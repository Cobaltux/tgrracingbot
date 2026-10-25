"""TGN Racing v4 — Control Room. Reutiliza .env, config.json y state.json.
No envía contenido ni cambia canales al arrancar. Requiere confirmación.
"""
import asyncio
import base64
import io
import json
import logging
import os
import re
from dataclasses import dataclass, field
from pathlib import Path
from urllib.parse import urlparse
import discord
from discord import app_commands
from dotenv import load_dotenv

BASE=Path(__file__).resolve().parent
load_dotenv(BASE/'.env',override=True)
TOKEN=os.getenv('DISCORD_TOKEN','').strip()
GUILD_ID=int(os.getenv('GUILD_ID','0') or 0)
SP=BASE/'state.json'
STATE=json.loads(SP.read_text(encoding='utf-8-sig')) if SP.exists() else {}
if STATE.get('guild_id',GUILD_ID)!=GUILD_ID:
    raise SystemExit('state.json pertenece a otro servidor. No lo borres.')
STATE['guild_id']=GUILD_ID
for k in ('roles','categories','channels','messages','tickets'):
    STATE.setdefault(k,{})
CONFIG=json.loads((BASE/'config.json').read_text(encoding='utf-8-sig')) if (BASE/'config.json').exists() else {}
logging.basicConfig(level=logging.INFO,format='%(levelname)s: %(message)s')
LOG=logging.getLogger('TGN')
LOCK=asyncio.Lock()
DRAFTS={}
MAX_BLOCKS=8
MAX_BYTES=8*1024*1024
FOUNDER=['Fundador']
STAFF=['Dirección','Staff']
TEAM=['Ingeniería','Piloto TGN','Piloto reserva']
# clave original, nombre visible; se reconocen nombres de versiones anteriores.
NAMES={
'bienvenida':'🏁・bienvenida','normativa':'📋・normativa','anuncios':'📢・comunicados',
'elige-tu-acceso':'🎟️・acceso-al-paddock','general':'💬・paddock','presentaciones':'👋・presentaciones',
'simracing':'🏎️・simracing','clips-y-capturas':'🎬・onboard-y-clips','hardware-y-setups':'🛠️・hardware-y-rigs',
'calendario':'🗓️・race-calendar','resultados':'🏆・race-results','noticias-lfm':'⛽・lfm-paddock','directos':'📺・race-live',
'briefing':'📌・race-briefing','entrenamientos':'⏱️・practice-sessions','telemetria-y-setups':'📊・telemetria-setups',
'estrategia':'🧠・race-strategy','debriefing':'📝・race-debrief','disponibilidad':'✅・disponibilidad',
'reclutamiento':'🔥・join-tgn','preguntas-frecuentes':'❓・guia-del-paddock','staff':'🔒・direccion',
'gestion-pilotos':'👥・driver-management','planificacion':'📐・sporting-planning','registro-bot':'⚙️・bot-control',
'Paddock • General':'🔊 Paddock | Lounge','Paddock • Simracing':'🏎️ Paddock | Simracing',
'Box TGN • 01':'🔴 BOX TGN | 01','Box TGN • 02':'🟡 BOX TGN | 02',
'Ingeniería • Radio':'🎧 Ingeniería | Radio','Dirección • Reunión':'🔒 Dirección | Meeting'}
CATS={
'01 ━ STARTING GRID':'01 ━ 🏁 STARTING GRID','02 ━ PADDOCK':'02 ━ 💬 THE PADDOCK',
'03 ━ RACE CONTROL':'03 ━ 🏆 RACE CONTROL','04 ━ TGN RACING · PRIVADO':'04 ━ 🔴 TGN RACING · TEAM',
'05 ━ ENTRA EN TGN':'05 ━ 🔥 JOIN THE GRID','06 ━ DIRECCIÓN · PRIVADO':'06 ━ 🔒 TEAM MANAGEMENT',
'07 ━ SOLICITUDES · PRIVADO':'07 ━ 🎟️ PRIVATE APPLICATIONS'}
STAFF_CHANNELS={'anuncios','calendario','resultados','noticias-lfm','briefing','entrenamientos','disponibilidad'}
TEAM_CHANNELS={'entrenamientos','disponibilidad','debriefing','clips-y-capturas'}


def save():
    tmp=SP.with_suffix('.tmp')
    tmp.write_text(json.dumps(STATE,ensure_ascii=False,indent=2),encoding='utf-8')
    tmp.replace(SP)


def role(g,name):
    mapped=g.get_role(STATE['roles'].get(name,0))
    if mapped:return mapped
    candidates=[r for r in g.roles if r.name==name]
    return candidates[0] if len(candidates)==1 else None


def level(member):
    if member.id==member.guild.owner_id:return 3
    ids={r.id for r in member.roles}
    for rank,names in [(3,FOUNDER),(2,STAFF),(1,TEAM)]:
        if any((r:=role(member.guild,n)) and r.id in ids for n in names):return rank
    return 0


def authorized(i):return i.guild is not None and i.guild.id==GUILD_ID


async def tell(i,text):
    if i.response.is_done():await i.followup.send(text,ephemeral=True)
    else:await i.response.send_message(text,ephemeral=True)


def normalize(s):
    return re.sub(r'[^a-z0-9áéíóúñ]+','',s.lower())


def resolve(g,key,category=False):
    bucket='categories' if category else 'channels'
    found=g.get_channel(STATE[bucket].get(key,0))
    if found:return found
    mapping=CATS if category else NAMES
    options={normalize(key),normalize(mapping.get(key,key))}
    pool=g.categories if category else g.channels
    matches=[c for c in pool if normalize(c.name) in options]
    return matches[0] if len(matches)==1 else None


def allowed(member,ch):
    if ch.guild.id!=GUILD_ID or not isinstance(ch,discord.TextChannel):return False
    rank=level(member)
    if rank==3:return True
    keys=STAFF_CHANNELS if rank==2 else TEAM_CHANNELS if rank==1 else set()
    return any((c:=resolve(ch.guild,k)) and c.id==ch.id for k in keys) and ch.permissions_for(member).view_channel


def logo_bytes():
    p=BASE/'logo_base64.txt'
    if p.exists():return base64.b64decode(p.read_text().strip())
    p=BASE/'logo-original.jpeg'
    return p.read_bytes() if p.exists() else None


def templates(g):
    def ref(k):
        c=resolve(g,k)
        return c.mention if c else '#'+NAMES.get(k,k)
    return {
'bienvenida':f'# 🏁 TGN RACING\n## BUILT TO COMPETE.\nDesde Tarragona, competimos con precisión, determinación y espíritu de equipo. Cada vuelta cuenta.\n\n### TU PRIMERA VUELTA\n**01** Lee {ref("normativa")}.\n**02** Acepta las normas en {ref("elige-tu-acceso")}.\n**03** Preséntate en {ref("presentaciones")}.\n**04** Si quieres competir, visita {ref("reclutamiento")}.\n\n**Tarragona, Catalunya · Fundado por HAF**\n-# Escudería virtual independiente. Sin afiliación oficial con LFM.',
'normativa':'# 📋 THE RACING CODE\n**La forma de competir también nos define.**\n\n**01 · RESPETO** Sin acoso, discriminación, amenazas ni ataques personales.\n**02 · FAIR PLAY** Sin trampas, exploits ni conducta antideportiva.\n**03 · PRIVACIDAD** No publiques datos personales, tokens ni contenido privado sin permiso.\n**04 · ORDEN** Usa cada canal para su función. Sin spam ni menciones masivas.\n**05 · EQUIPO** Los recursos privados se quedan dentro del equipo.\n**06 · CONFLICTOS** Contexto y pruebas al staff; nada de hostigamiento público.\n**07 · MODERACIÓN** Sigue las indicaciones del staff.\n\nAceptar las normas no verifica tu identidad ni te convierte en piloto.',
'elige-tu-acceso':f'# 🎟️ YOUR PADDOCK PASS\nLee {ref("normativa")} y pulsa **Aceptar normas** para obtener Comunidad.\n\nAcceso a conversación, clips y salas públicas. No concede acceso a pilotos, dirección ni solicitudes ajenas.',
'anuncios':'# 📢 TEAM BULLETIN\n**Información confirmada del equipo.**\n\nAquí publicaremos comunicados y novedades oficiales de TGN Racing.\nPor ahora no hay anuncios publicados. No se anuncian fichajes, acuerdos o competiciones sin confirmar.',
'calendario':'# 🗓️ NEXT ON THE GRID\nPróximamente anunciaremos nuestras próximas carreras.\n\nCada evento indicará serie, circuito, categoría, fecha y zona horaria, participantes y enlace real si existe.\n-# Actualización manual. Sin sincronización automática con LFM.',
'resultados':'# 🏆 THE FINISH LINE\n**Los resultados se ganan en pista.**\nTodavía no hay clasificaciones verificadas publicadas.\n\nPublicaremos fecha, serie, circuito, piloto, posición, mejor vuelta e incidentes cuando estén confirmados. Un dato pendiente no significa cero.',
'reclutamiento':'# 🔥 EARN YOUR PLACE\n**¿Tienes lo necesario para competir?**\nRespeto, constancia y mentalidad colectiva.\n\n**01 · Presentación** Experiencia, disponibilidad y objetivos.\n**02 · Conversación** Expectativas y encaje.\n**03 · Valoración** El equipo confirmará condiciones y posibles pruebas.\n\nPulsa **Solicitar plaza** para abrir una solicitud privada. No garantiza incorporación ni plazo de respuesta. Staff y administradores podrán leerla. No envíes datos sensibles.',
'briefing':'# 📌 RACE BRIEFING\n**Zona privada · solo equipo**\n\nAntes de cada carrera: evento y reglamento, circuito, categoría, fecha con zona horaria, pilotos, condiciones, combustible, neumáticos, estrategia y canal de radio.\n\nCompletar con información confirmada. No divulgar fuera del equipo.',
'entrenamientos':'# ⏱️ PRACTICE WITH PURPOSE\nEntrenar no es solo acumular vueltas.\n\nIndica fecha y zona horaria, coche, circuito, condiciones y objetivo técnico. Al terminar, comparte una conclusión y el siguiente punto a trabajar.',
'debriefing':'# 📝 REVIEW. RESET. IMPROVE.\nAnalizamos decisiones, no buscamos culpables.\n\n**Qué funcionó** · Hechos concretos.\n**Qué mejorar** · Contexto y referencias.\n**Qué aprendimos** · Conclusión útil.\n**Siguiente acción** · Objetivo acordado.',
'disponibilidad':'# ✅ DRIVER AVAILABILITY\nIndica evento, fecha y zona horaria, y estado: disponible, pendiente o no disponible.\nActualízalo si cambia. No hace falta compartir motivos personales.',
'preguntas-frecuentes':'# ❓ PADDOCK GUIDE\n**Acceso:** acepta las normas en el panel público.\n**Pilotos:** una candidatura requiere valoración del equipo.\n**LFM:** no hay importación automática de resultados.\n**Privacidad:** las solicitudes son mensajes de Discord; pide al staff su eliminación cuando corresponda.\n**Botones:** requieren que el bot esté conectado.',
'general':'# 💬 THE PADDOCK\nEl punto de encuentro de TGN. Carreras, actualidad y conversación entre sesiones.\n**Competición en pista. Respeto siempre.**',
'presentaciones':'# 👋 MEET THE GRID\nPreséntate con tu alias, simulador, coche o categoría favorita y objetivos.\nNo necesitas publicar nombre real, edad ni ubicación exacta.',
'simracing':'# 🏎️ RACING TALK\nTécnica, simuladores y circuitos. Al pedir ayuda, indica coche, circuito, condiciones y qué has probado. Distingue opiniones de reglas oficiales.',
'clips-y-capturas':'# 🎬 ONBOARD ROOM\nComparte vueltas, adelantamientos y momentos para aprender. Indica simulador, circuito y qué quieres mostrar. No uses clips para acosar o ridiculizar.',
'hardware-y-setups':'# 🛠️ THE SIM LAB\nVolantes, pedales, rigs y ajustes. Para una incidencia: modelo, sistema y síntomas. No publiques credenciales ni datos de compra sensibles.',
'noticias-lfm':'# ⛽ LFM PADDOCK\nNoticias contrastadas y fuentes reales.\nhttps://lowfuelmotorsport.com/\n-# Plataforma general; no es un perfil del equipo ni implica afiliación oficial.',
'directos':'# 📺 RACE LIVE\nComparte emisiones relacionadas con simracing. Indica título, plataforma y horario. No retransmitas reuniones o estrategias privadas sin permiso.',
'estrategia':'# 🧠 RACE STRATEGY\nPlan base, consumo, stints, ventanas de parada y contingencias. Verifica las reglas y los supuestos antes de dar una estrategia por definitiva.',
'telemetria-y-setups':'# 📊 DATA DRIVEN\nCada referencia debe indicar coche, circuito, versión y condiciones. Explica qué cambiaste y qué efecto observaste. No distribuyas recursos ajenos sin permiso.',
'staff':'# 🔒 TEAM MANAGEMENT\nCoordinación interna. Revisa accesos, solicitudes y retención de datos.\nEl panel separa herramientas de Fundador, Staff y Equipo. No concede Administrator a ningún rol.',
'gestion-pilotos':'# 👥 DRIVER MANAGEMENT\nSeguimiento de solicitudes y decisiones deportivas. Registra solo datos necesarios. Nunca recopiles contraseñas ni documentos de identidad.',
'planificacion':'# 📐 SPORTING PLAN\nObjetivo, acciones, responsables y revisión. Distingue propuestas de compromisos confirmados.',
'registro-bot':'# ⚙️ CONTROL ROOM\n`/panel` abre las herramientas permitidas para tu rol.\n`/archivo` añade una foto o documento a tu borrador.\n`/estado` muestra el diagnóstico al Fundador.\nNo hay AutoMod, antiraid ni integración automática con LFM.',
}


@dataclass
class Block:
    kind:str
    text:str=''
    data:bytes=b''
    filename:str=''


@dataclass
class Draft:
    blocks:list=field(default_factory=list)
    channel_id:int=0
    selected:int=0


def draft(uid):return DRAFTS.setdefault(uid,Draft())


def add_block(uid,block):
    d=draft(uid)
    if len(d.blocks)>=MAX_BLOCKS:raise ValueError('Máximo 8 bloques. Elimina uno antes de añadir otro.')
    if sum(len(b.data) for b in d.blocks)+len(block.data)>24*1024*1024:raise ValueError('Máximo 24 MB por borrador.')
    d.blocks.append(block)
    d.selected=len(d.blocks)-1


def summary(d):
    lines=['# ✍️ AÑADIR MENSAJES','Ordena los bloques con el selector y las flechas. Cada bloque se publicará como un mensaje, en ese orden.','']
    lines.append(f'**Destino:** <#{d.channel_id}>' if d.channel_id else '**Destino:** pendiente de seleccionar')
    for n,b in enumerate(d.blocks,1):
        detail=b.filename if b.kind=='archivo' else b.text.replace('\n',' ')[:90]
        lines.append(f'**{n:02} · {b.kind.upper()}** — {discord.utils.escape_markdown(detail)}')
    if not d.blocks:lines.append('Borrador vacío: añade texto, enlace, plantilla o archivo.')
    lines.append('\nFotos/documentos: usa `/archivo` y vuelve a abrir el editor. Ningún bloque se publica hasta confirmar. Los borradores se pierden al reiniciar.')
    return '\n'.join(lines)


class SecureView(discord.ui.View):
    def __init__(self,uid=None,minlevel=1,timeout=900):
        super().__init__(timeout=timeout)
        self.uid=uid
        self.minlevel=minlevel
    async def interaction_check(self,i):
        if not authorized(i) or (self.uid is not None and i.user.id!=self.uid) or level(i.user)<self.minlevel:
            await tell(i,'🔒 No tienes acceso a esta herramienta o el panel pertenece a otra persona.')
            return False
        return True


class TextModal(discord.ui.Modal,title='Añadir un bloque de texto'):
    body=discord.ui.TextInput(label='Texto (admite formato de Discord)',style=discord.TextStyle.paragraph,max_length=1800)
    def __init__(self,uid):super().__init__();self.uid=uid
    async def on_submit(self,i):
        if i.user.id!=self.uid or not authorized(i) or level(i.user)<1:return await tell(i,'Sin acceso.')
        try:add_block(i.user.id,Block('texto',text=self.body.value))
        except ValueError as e:return await tell(i,str(e))
        await i.response.send_message(summary(draft(i.user.id)),view=Composer(i.user.id),ephemeral=True)


class LinkModal(discord.ui.Modal,title='Añadir un enlace'):
    url=discord.ui.TextInput(label='URL completa https://',max_length=1200)
    label=discord.ui.TextInput(label='Descripción opcional',required=False,max_length=150)
    def __init__(self,uid):super().__init__();self.uid=uid
    async def on_submit(self,i):
        if i.user.id!=self.uid or not authorized(i) or level(i.user)<1:return await tell(i,'Sin acceso.')
        u=self.url.value.strip();parsed=urlparse(u)
        if parsed.scheme not in ('http','https') or not parsed.netloc:return await tell(i,'Introduce una URL http o https válida.')
        content=(self.label.value.strip()+'\n' if self.label.value.strip() else '')+u
        try:add_block(i.user.id,Block('enlace',text=content))
        except ValueError as e:return await tell(i,str(e))
        await i.response.send_message(summary(draft(i.user.id)),view=Composer(i.user.id),ephemeral=True)


class TargetSelect(discord.ui.ChannelSelect):
    def __init__(self):super().__init__(placeholder='1 · Selecciona el canal de destino',channel_types=[discord.ChannelType.text],min_values=1,max_values=1,row=0)
    async def callback(self,i):
        ch=i.guild.get_channel(self.values[0].id)
        if not ch or not allowed(i.user,ch):return await tell(i,'Tu rol no puede publicar en ese canal desde el bot.')
        draft(i.user.id).channel_id=ch.id
        await i.response.edit_message(content=summary(draft(i.user.id)),view=Composer(i.user.id))


class BlockSelect(discord.ui.Select):
    def __init__(self,d):
        options=[discord.SelectOption(label=f'{n+1:02} · {b.kind} · {(b.filename or b.text[:45]).replace(chr(10)," ")}'[:100],value=str(n),default=n==d.selected) for n,b in enumerate(d.blocks)]
        super().__init__(placeholder='2 · Elige el bloque que quieres mover o quitar',options=options or [discord.SelectOption(label='Sin bloques',value='0')],disabled=not d.blocks,row=1)
    async def callback(self,i):
        draft(i.user.id).selected=int(self.values[0])
        await i.response.edit_message(content=summary(draft(i.user.id)),view=Composer(i.user.id))


class TemplateSelect(discord.ui.Select):
    def __init__(self,g,rank):
        keys=['bienvenida','normativa','anuncios','elige-tu-acceso','reclutamiento','calendario','resultados','briefing','entrenamientos','debriefing','disponibilidad']
        if rank==2:keys=[k for k in keys if k in STAFF_CHANNELS]
        if rank==1:keys=[k for k in keys if k in TEAM_CHANNELS]
        super().__init__(placeholder='Elige una plantilla para tu borrador',options=[discord.SelectOption(label=k.upper(),value=k) for k in keys])
    async def callback(self,i):
        key=self.values[0]
        try:add_block(i.user.id,Block('texto',text=templates(i.guild)[key]))
        except ValueError as e:return await tell(i,str(e))
        ch=resolve(i.guild,key)
        if ch and allowed(i.user,ch):draft(i.user.id).channel_id=ch.id
        await i.response.send_message(summary(draft(i.user.id)),view=Composer(i.user.id),ephemeral=True)


async def send_block(destination,b,ephemeral=False):
    kwargs={'allowed_mentions':discord.AllowedMentions.none()}
    if ephemeral:kwargs['ephemeral']=True
    if b.kind=='archivo':kwargs['file']=discord.File(io.BytesIO(b.data),filename=b.filename)
    else:kwargs['content']=b.text
    return await destination.send(**kwargs)


class PublishConfirm(SecureView):
    def __init__(self,uid,cid,blocks):
        super().__init__(uid,timeout=180)
        self.cid=cid
        self.blocks=tuple(Block(b.kind,b.text,b.data,b.filename) for b in blocks)
        self.done=False
    @discord.ui.button(label='Confirmar envío en este orden',style=discord.ButtonStyle.danger,emoji='📢')
    async def publish(self,i,button):
        if self.done:return await tell(i,'Este envío ya fue utilizado. No se repetirá.')
        ch=i.guild.get_channel(self.cid)
        if not ch or not allowed(i.user,ch):return await tell(i,'Tu rol ya no puede publicar en el destino aprobado.')
        perms=ch.permissions_for(i.guild.me)
        if not perms.view_channel or not perms.send_messages:return await tell(i,'El bot no puede ver o escribir en el destino.')
        if any(b.kind=='archivo' for b in self.blocks) and not perms.attach_files:return await tell(i,'Falta Adjuntar archivos en el destino.')
        self.done=True
        await i.response.defer(ephemeral=True,thinking=True)
        button.disabled=True
        await i.edit_original_response(view=self)
        sent=[]
        try:
            async with LOCK:
                for b in self.blocks:
                    if b.kind=='archivo' and len(b.data)>i.guild.filesize_limit:raise ValueError('Un archivo supera el límite actual de este servidor.')
                    sent.append(await send_block(ch,b))
            await tell(i,f'✅ Publicados {len(sent)} bloques en {ch.mention}, en el orden aprobado.\nPrimer mensaje: {sent[0].jump_url}\nEl borrador se conserva; vacíalo cuando termines para no reutilizarlo por error.')
        except Exception as e:
            LOG.exception('Envío parcial')
            await tell(i,f'⚠️ Se enviaron {len(sent)}/{len(self.blocks)} bloques. No se reintentó automáticamente ni se borró nada. Error: {type(e).__name__}. Revisa el canal antes de repetir.')


class Composer(SecureView):
    def __init__(self,uid):
        super().__init__(uid)
        self.add_item(TargetSelect());self.add_item(BlockSelect(draft(uid)))
    @discord.ui.button(label='Texto',emoji='📝',style=discord.ButtonStyle.secondary,row=2)
    async def text(self,i,b):await i.response.send_modal(TextModal(i.user.id))
    @discord.ui.button(label='Enlace',emoji='🔗',style=discord.ButtonStyle.secondary,row=2)
    async def link(self,i,b):await i.response.send_modal(LinkModal(i.user.id))
    @discord.ui.button(label='Foto / archivo',emoji='📎',style=discord.ButtonStyle.secondary,row=2)
    async def file(self,i,b):await tell(i,'Usa `/archivo` en Discord y adjunta una foto o documento. Se añadirá al final de tu borrador. Después vuelve a abrir Añadir mensajes para moverlo. Máximo 8 MB por archivo y 24 MB por borrador.')
    @discord.ui.button(label='Plantilla',emoji='🏁',style=discord.ButtonStyle.secondary,row=2)
    async def template(self,i,b):
        v=SecureView(i.user.id);v.add_item(TemplateSelect(i.guild,level(i.user)))
        await i.response.send_message('Selecciona una plantilla. Puedes quitar su bloque y escribir tu propio texto antes de publicar.',view=v,ephemeral=True)
    @discord.ui.button(label='Subir',emoji='⬆️',style=discord.ButtonStyle.secondary,row=3)
    async def up(self,i,b):
        d=draft(i.user.id);s=d.selected
        if 0<s<len(d.blocks):d.blocks[s-1],d.blocks[s]=d.blocks[s],d.blocks[s-1];d.selected-=1
        await i.response.edit_message(content=summary(d),view=Composer(i.user.id))
    @discord.ui.button(label='Bajar',emoji='⬇️',style=discord.ButtonStyle.secondary,row=3)
    async def down(self,i,b):
        d=draft(i.user.id);s=d.selected
        if 0<=s<len(d.blocks)-1:d.blocks[s+1],d.blocks[s]=d.blocks[s],d.blocks[s+1];d.selected+=1
        await i.response.edit_message(content=summary(d),view=Composer(i.user.id))
    @discord.ui.button(label='Quitar bloque',style=discord.ButtonStyle.secondary,row=3)
    async def remove(self,i,b):
        d=draft(i.user.id)
        if d.blocks:d.blocks.pop(min(d.selected,len(d.blocks)-1));d.selected=max(0,min(d.selected,len(d.blocks)-1))
        await i.response.edit_message(content=summary(d),view=Composer(i.user.id))
    @discord.ui.button(label='Vaciar borrador',style=discord.ButtonStyle.secondary,row=3)
    async def clear(self,i,b):
        DRAFTS[i.user.id]=Draft()
        await i.response.edit_message(content=summary(draft(i.user.id)),view=Composer(i.user.id))
    @discord.ui.button(label='Vista previa y publicar',emoji='👁️',style=discord.ButtonStyle.danger,row=4)
    async def preview(self,i,b):
        d=draft(i.user.id);ch=i.guild.get_channel(d.channel_id)
        if not ch or not allowed(i.user,ch):return await tell(i,'Selecciona un destino permitido para tu rol.')
        if not d.blocks:return await tell(i,'Añade al menos un bloque.')
        blocks=tuple(Block(x.kind,x.text,x.data,x.filename) for x in d.blocks)
        await i.response.defer(ephemeral=True,thinking=True)
        await tell(i,f'**VISTA PREVIA PRIVADA · destino: {ch.mention}**\nCada bloque aparecerá como un mensaje separado. Las fotos pueden mostrarse como adjuntos según el cliente y el tipo de archivo.')
        try:
            for block in blocks:await send_block(i.followup,block,ephemeral=True)
            await i.followup.send(f'¿Publicar estos **{len(blocks)} bloques** en {ch.mention}, exactamente en este orden? No se notificará a @everyone ni a roles.',view=PublishConfirm(i.user.id,ch.id,blocks),ephemeral=True,allowed_mentions=discord.AllowedMentions.none())
        except discord.HTTPException:
            LOG.exception('Vista previa fallida')
            await tell(i,'No se pudo completar la vista previa. No se ha enviado nada al canal público.')


class AccessView(discord.ui.View):
    def __init__(self):super().__init__(timeout=None)
    @discord.ui.button(label='Aceptar normas',emoji='🏁',style=discord.ButtonStyle.danger,custom_id='tgn:community:v1')
    async def accept(self,i,b):
        if not authorized(i):return await tell(i,'Servidor no autorizado.')
        r=role(i.guild,'Comunidad')
        if not r:return await tell(i,'Falta el rol Comunidad.')
        await i.response.defer(ephemeral=True)
        try:await i.user.add_roles(r,reason='Aceptación de normas TGN');await tell(i,'🏁 Acceso a Comunidad habilitado. Esto no concede acceso a pilotos ni staff.')
        except discord.HTTPException:await tell(i,'El bot no puede asignar Comunidad. Revisa Gestionar roles y la posición del bot.')


class Application(discord.ui.Modal,title='TGN Racing · Solicitar plaza'):
    alias=discord.ui.TextInput(label='Alias',max_length=70)
    experience=discord.ui.TextInput(label='Simulador y experiencia',style=discord.TextStyle.paragraph,max_length=700)
    availability=discord.ui.TextInput(label='Disponibilidad y objetivos',style=discord.TextStyle.paragraph,max_length=700)
    async def on_submit(self,i):
        if not authorized(i):return await tell(i,'Servidor no autorizado.')
        await i.response.defer(ephemeral=True)
        async with LOCK:
            uid=str(i.user.id);old=STATE['tickets'].get(uid,{})
            ch=i.guild.get_channel(old.get('channel',0))
            if ch:return await tell(i,f'Ya tienes solicitud: {ch.mention}. Staff puede reabrirla si está cerrada.')
            cat=resolve(i.guild,'07 ━ SOLICITUDES · PRIVADO',True)
            if not cat:return await tell(i,'No se reconoce la categoría de solicitudes. Contacta con Fundador.')
            if len(cat.channels)>=45:return await tell(i,'La bandeja está llena. Contacta con staff.')
            perms={i.guild.default_role:discord.PermissionOverwrite(view_channel=False),i.guild.me:discord.PermissionOverwrite(view_channel=True,send_messages=True,read_message_history=True),i.user:discord.PermissionOverwrite(view_channel=True,send_messages=True,read_message_history=True)}
            for name in FOUNDER+STAFF:
                r=role(i.guild,name)
                if r:perms[r]=discord.PermissionOverwrite(view_channel=True,send_messages=True,read_message_history=True)
            ch=await i.guild.create_text_channel(f'🎟️・solicitud-{i.user.id}',category=cat,overwrites=perms,reason='Solicitud voluntaria TGN')
            STATE['tickets'][uid]={'channel':ch.id,'closed':False};save()
            await ch.send(f'# 🎟️ SOLICITUD PRIVADA\nSolicitante: {i.user.mention}\nStaff y administradores pueden leerla. No envíes datos sensibles.')
            for label,value in [('ALIAS',self.alias.value),('EXPERIENCIA',self.experience.value),('DISPONIBILIDAD Y OBJETIVOS',self.availability.value)]:await ch.send(f'## {label}\n{discord.utils.escape_markdown(value)}')
            await tell(i,f'Solicitud creada: {ch.mention}. No se garantiza una plaza ni plazo de respuesta.')


class RecruitmentView(discord.ui.View):
    def __init__(self):super().__init__(timeout=None)
    @discord.ui.button(label='Solicitar plaza',emoji='🏎️',style=discord.ButtonStyle.danger,custom_id='tgn:apply:v1')
    async def apply(self,i,b):
        if not authorized(i):return await tell(i,'Servidor no autorizado.')
        await i.response.send_modal(Application())


class MaintenanceConfirm(SecureView):
    def __init__(self,uid,action,plan):
        super().__init__(uid,3,180);self.action=action;self.plan=plan;self.used=False
    @discord.ui.button(label='Confirmar los cambios indicados',style=discord.ButtonStyle.danger)
    async def confirm(self,i,b):
        if self.used:return await tell(i,'Confirmación ya utilizada.')
        self.used=True
        await i.response.defer(ephemeral=True,thinking=True)
        b.disabled=True;await i.edit_original_response(view=self)
        done=0;errors=[]
        async with LOCK:
            for item in self.plan:
                try:
                    if self.action=='channels':
                        bucket,key,cid,name=item;ch=i.guild.get_channel(cid)
                        if not ch:raise ValueError('Canal ya no disponible')
                        if ch.name!=name:await ch.edit(name=name,reason=f'Renovación TGN confirmada por {i.user.id}');done+=1
                        STATE[bucket][key]=cid;save()
                    else:
                        key,cid,text=item;ch=i.guild.get_channel(cid)
                        if not ch:raise ValueError('Canal ya no disponible')
                        view=AccessView() if key=='elige-tu-acceso' else RecruitmentView() if key=='reclutamiento' else None
                        previous=None
                        if STATE['messages'].get(key):
                            try:
                                candidate=await ch.fetch_message(STATE['messages'][key])
                                if candidate.author.id==client.user.id:previous=candidate
                            except discord.NotFound:pass
                        if previous:msg=await previous.edit(content=text,embed=None,attachments=[],view=view,allowed_mentions=discord.AllowedMentions.none())
                        else:msg=await ch.send(content=text,view=view,allowed_mentions=discord.AllowedMentions.none())
                        STATE['channels'][key]=cid;STATE['messages'][key]=msg.id;save();done+=1
                except Exception as e:
                    LOG.exception('Error en %s',item[0]);errors.append(f'{item[1] if self.action=="channels" else item[0]}: {type(e).__name__}')
        result=f'✅ {done} {"nombres modificados" if self.action=="channels" else "paneles publicados o actualizados"}.'
        if errors:result+='\n⚠️ '+ '\n'.join(errors[:12])+'\nRevisa el error detallado en la consola.'
        if not done and not errors:result+=' Los nombres ya coincidían; se han guardado los canales reconocidos.'
        await tell(i,result+'\nNo se han borrado conversaciones ni cambiado permisos o posiciones de roles.')


async def maintenance(i,action):
    if not authorized(i) or level(i.user)<3:return await tell(i,'Solo Fundador o el propietario del servidor.')
    plan=[];missing=[]
    if action=='channels':
        for bucket,mapping in [('categories',CATS),('channels',NAMES)]:
            for key,name in mapping.items():
                ch=resolve(i.guild,key,bucket=='categories')
                if ch:plan.append((bucket,key,ch.id,name))
                else:missing.append(key)
        changes=[x for x in plan if i.guild.get_channel(x[2]).name!=x[3]]
        overview='\n'.join(f'<#{cid}> → **{name}**' for _,_,cid,name in changes)
        intro=f'## 🎨 RENOVAR CANALES\nReconocidos: {len(plan)}. Cambios de nombre: {len(changes)}.\nNo se crean canales duplicados ni se cambian permisos.\n'
    else:
        for key,text in templates(i.guild).items():
            ch=resolve(i.guild,key)
            if isinstance(ch,discord.TextChannel):plan.append((key,ch.id,text))
            else:missing.append(key)
        overview='\n'.join(f'• {key} → <#{cid}>' for key,cid,_ in plan)
        intro='## 🏁 PUBLICAR PANELES INICIALES\nSe publicará texto visible en los destinos siguientes. Se reemplaza el panel del bot registrado, no la conversación. Guarda cualquier personalización previa.\n'
    report=intro+overview
    if missing:report+='\n\n**No reconocidos (sin cambios):** '+', '.join(missing)
    if not plan:return await tell(i,'No se reconoce ningún canal. No se ha cambiado nada. Conserva el state.json original y usa /estado para revisar los IDs.')
    # Divide el informe sin perder el detalle de objetivos aprobados.
    await i.response.defer(ephemeral=True)
    for start in range(0,len(report),1800):await i.followup.send(report[start:start+1800],ephemeral=True,allowed_mentions=discord.AllowedMentions.none())
    await i.followup.send('Revisa el informe anterior. ¿Confirmas estos destinos y cambios?',view=MaintenanceConfirm(i.user.id,action,plan),ephemeral=True)


class ControlPanel(SecureView):
    def __init__(self):super().__init__(uid=None,minlevel=0,timeout=None)
    @discord.ui.button(label='Añadir mensajes',emoji='✍️',style=discord.ButtonStyle.danger,custom_id='tgn:v4:compose',row=0)
    async def compose(self,i,b):
        if level(i.user)<1:return await tell(i,'Solo Fundador, Staff o Equipo pueden componer publicaciones.')
        await i.response.send_message(summary(draft(i.user.id)),view=Composer(i.user.id),ephemeral=True)
    @discord.ui.button(label='Paneles iniciales · Fundador',emoji='🏁',style=discord.ButtonStyle.secondary,custom_id='tgn:v4:seed',row=0)
    async def seed(self,i,b):await maintenance(i,'seed')
    @discord.ui.button(label='Renovar canales · Fundador',emoji='🎨',style=discord.ButtonStyle.secondary,custom_id='tgn:v4:channels',row=1)
    async def channels(self,i,b):await maintenance(i,'channels')
    @discord.ui.button(label='Bienvenida + logo · Fundador',emoji='🛡️',style=discord.ButtonStyle.secondary,custom_id='tgn:v4:welcome',row=1)
    async def welcome(self,i,b):
        if level(i.user)<3:return await tell(i,'Solo Fundador.')
        d=draft(i.user.id)
        if d.blocks:return await tell(i,'Tu borrador tiene contenido. Ábrelo y vacíalo antes de cargar bienvenida y logo.')
        original=logo_bytes()
        if original:add_block(i.user.id,Block('archivo',data=original,filename='tgn-logo.jpeg'))
        add_block(i.user.id,Block('texto',text=templates(i.guild)['bienvenida']))
        ch=resolve(i.guild,'bienvenida')
        if ch:d.channel_id=ch.id
        await i.response.send_message(summary(d),view=Composer(i.user.id),ephemeral=True)
    @discord.ui.button(label='Mi acceso y ayuda',emoji='❓',style=discord.ButtonStyle.secondary,custom_id='tgn:v4:help',row=2)
    async def help(self,i,b):
        names={0:'Comunidad',1:'Equipo',2:'Staff',3:'Fundador / propietario'}
        await tell(i,f'**Tu nivel: {names[level(i.user)]}**\nFundador: mensajes a cualquier canal de texto, renovación y paneles iniciales.\nStaff: anuncios, calendario, resultados, LFM, briefing, entrenamientos y disponibilidad que pueda ver.\nEquipo: entrenamientos, disponibilidad, debriefing y clips que pueda ver.\nComunidad: aceptar normas y solicitar plaza; sin herramientas de publicación.\n\nFotos/documentos: `/archivo`. Cada bloque se envía como un mensaje separado; puedes moverlo arriba/abajo. No hay envío automático al arrancar ni menciones masivas.\nLos paneles privados del editor caducan a los 15 minutos; abre uno nuevo con /panel. El bot necesita seguir encendido.')


class Client(discord.Client):
    def __init__(self):
        super().__init__(intents=discord.Intents.default(),allowed_mentions=discord.AllowedMentions.none())
        self.tree=app_commands.CommandTree(self)
    async def setup_hook(self):
        self.add_view(ControlPanel());self.add_view(AccessView());self.add_view(RecruitmentView())
        target=discord.Object(id=GUILD_ID);self.tree.copy_global_to(guild=target);await self.tree.sync(guild=target)
    async def on_ready(self):LOG.info('TGN CONTROL ROOM v4 conectado. Ejecuta /panel. No se publica ni renombra nada al arrancar.')


client=Client()


@client.tree.command(name='panel',description='Abrir Control Room de TGN según tus permisos')
async def panel(i:discord.Interaction):
    if not authorized(i):return await tell(i,'Servidor no autorizado.')
    await i.response.send_message('# 🏁 TGN RACING · CONTROL ROOM\n**BUILT TO COMPETE.**\n\n✍️ Crea publicaciones con texto, fotos, documentos y enlaces en el orden que quieras.\n🎨 Fundador puede renovar nombres y publicar paneles iniciales.\n🔒 Cada acción comprueba tu rol, incluso al pulsar sus botones.\n\nNada se publica sin vista previa o confirmación.',view=ControlPanel(),ephemeral=True)


@client.tree.command(name='archivo',description='Añadir foto o documento al borrador; no lo publica')
async def archivo(i:discord.Interaction,adjunto:discord.Attachment):
    if not authorized(i) or level(i.user)<1:return await tell(i,'Solo Fundador, Staff o Equipo.')
    if adjunto.size>min(MAX_BYTES,i.guild.filesize_limit):return await tell(i,'Archivo demasiado grande. Máximo 8 MB o el límite inferior del servidor.')
    if len(draft(i.user.id).blocks)>=MAX_BLOCKS:return await tell(i,'El borrador ya tiene 8 bloques. Quita uno antes de adjuntar.')
    await i.response.defer(ephemeral=True)
    try:
        data=await adjunto.read()
        name=Path(adjunto.filename.replace('\\','/')).name
        add_block(i.user.id,Block('archivo',data=data,filename=name))
        await i.followup.send(summary(draft(i.user.id)),view=Composer(i.user.id),ephemeral=True)
    except ValueError as e:await tell(i,str(e))
    except discord.HTTPException:await tell(i,'No se pudo descargar el adjunto desde Discord. Inténtalo de nuevo.')


@client.tree.command(name='renovar',description='Fundador: revisar y confirmar nuevos nombres de canales')
async def renovar(i:discord.Interaction):await maintenance(i,'channels')


@client.tree.command(name='instalar',description='Fundador: revisar y publicar paneles en canales existentes')
async def instalar(i:discord.Interaction):await maintenance(i,'seed')


@client.tree.command(name='estado',description='Fundador: comprobar canales reconocidos y permisos')
async def estado(i:discord.Interaction):
    if not authorized(i) or level(i.user)<3:return await tell(i,'Solo Fundador.')
    rows=[]
    for key in NAMES:
        ch=resolve(i.guild,key)
        rows.append(f'{"✅" if ch else "❌"} {key}'+(f' → {ch.id}' if ch else ' (no reconocido o ambiguo)'))
    report='**TGN v4 · DIAGNÓSTICO**\n'+'\n'.join(rows)
    await i.response.defer(ephemeral=True)
    for start in range(0,len(report),1800):await i.followup.send(report[start:start+1800],ephemeral=True)
    p=i.guild.me.guild_permissions
    await tell(i,f'Gestionar canales: {p.manage_channels}\nGestionar roles: {p.manage_roles}\nAdjuntar archivos: {p.attach_files}\nNo se han cambiado permisos ni enviado mensajes a canales.')


@client.tree.command(name='piloto',description='Fundador: asignar o retirar Piloto TGN')
async def piloto(i:discord.Interaction,miembro:discord.Member,activar:bool):
    if not authorized(i) or level(i.user)<3:return await tell(i,'Solo Fundador.')
    r=role(i.guild,'Piloto TGN')
    if not r:return await tell(i,'No se reconoce Piloto TGN.')
    await i.response.defer(ephemeral=True)
    if activar:await miembro.add_roles(r,reason=f'Alta autorizada por {i.user.id}')
    else:await miembro.remove_roles(r,reason=f'Baja autorizada por {i.user.id}')
    await tell(i,'Rol actualizado. Otros roles pueden seguir dando acceso; revísalos por separado.')


@client.tree.command(name='cerrar',description='Staff: cerrar solicitud actual sin borrar mensajes')
async def cerrar(i:discord.Interaction):
    if not authorized(i) or level(i.user)<2:return await tell(i,'Solo Staff o Fundador.')
    entry=next(((uid,t) for uid,t in STATE['tickets'].items() if t.get('channel')==i.channel_id),None)
    if not entry:return await tell(i,'Usa este comando dentro de una solicitud del bot.')
    await i.response.defer(ephemeral=True)
    uid,t=entry
    try:member=await i.guild.fetch_member(int(uid))
    except discord.NotFound:member=None
    if member:await i.channel.set_permissions(member,view_channel=True,send_messages=False,read_message_history=True,reason='Solicitud cerrada')
    t['closed']=True;save()
    await i.channel.send('## 🔒 SOLICITUD CERRADA\nSe conserva la conversación. Staff puede reabrirla o eliminarla manualmente. Los administradores conservan su acceso.')
    await tell(i,'Solicitud cerrada sin borrar mensajes.')


@client.tree.error
async def command_error(i:discord.Interaction,error):
    original=getattr(error,'original',error)
    LOG.error('Error de comando',exc_info=(type(original),original,original.__traceback__))
    detail=f'Discord {original.status}, código {original.code}' if isinstance(original,discord.HTTPException) else type(original).__name__
    await tell(i,'No se pudo completar: '+detail+'. Revisa la consola. No se ha reintentado automáticamente.')


if __name__=='__main__':
    if not TOKEN or not GUILD_ID:raise SystemExit('Completa DISCORD_TOKEN y GUILD_ID en .env. No compartas el token.')
    client.run(TOKEN,log_level=logging.INFO)

import threading
from http.server import HTTPServer, BaseHTTPRequestHandler

class HealthCheckHandler(BaseHTTPRequestHandler):
    def do_GET(self):
        self.send_response(200)
        self.end_headers()
        self.wfile.write(b"OK")

def run_health_check():
    server = HTTPServer(('0.0.0.0', 10000), HealthCheckHandler)
    server.serve_forever()