"""TGN Racing — instalador revisado. Conserva .env, config.json y state.json.
No ordena roles, no asigna Fundador automáticamente y no borra canales.
"""
import asyncio
import base64
import io
import json
import logging
import os
from pathlib import Path

import discord
from discord import app_commands
from dotenv import load_dotenv

BASE = Path(__file__).resolve().parent
load_dotenv(BASE / '.env', override=True)
TOKEN = os.getenv('DISCORD_TOKEN', '').strip()
GUILD_ID = int(os.getenv('GUILD_ID', '0').strip() or '0')
CONFIG = json.loads((BASE / 'config.json').read_text(encoding='utf-8-sig'))
STATE_FILE = BASE / 'state.json'
STATE = json.loads(STATE_FILE.read_text(encoding='utf-8-sig')) if STATE_FILE.exists() else {}
if STATE.get('guild_id', GUILD_ID) != GUILD_ID:
    raise SystemExit('state.json pertenece a otro servidor. No lo borres: usa otra carpeta.')
STATE['guild_id'] = GUILD_ID
for key in ['roles', 'categories', 'channels', 'messages', 'tickets']:
    STATE.setdefault(key, {})
logging.basicConfig(level=logging.INFO, format='%(levelname)s: %(message)s')
LOG = logging.getLogger('TGN')
INSTALL_LOCK = asyncio.Lock()
TICKET_LOCK = asyncio.Lock()
ROLES = {}
STAFF = ['Fundador', 'Dirección', 'Staff']
TEAM = STAFF + ['Ingeniería', 'Piloto TGN', 'Piloto reserva']


def save():
    temp = STATE_FILE.with_suffix('.tmp')
    temp.write_text(json.dumps(STATE, ensure_ascii=False, indent=2), encoding='utf-8')
    temp.replace(STATE_FILE)


def role(guild, name):
    rid = STATE['roles'].get(name, 0)
    return ROLES.get(rid) or guild.get_role(rid)


def channel(guild, name):
    return guild.get_channel(STATE['channels'].get(name, 0))


def authorized(i):
    return i.guild is not None and i.guild.id == GUILD_ID


def staff(member):
    return member.guild_permissions.administrator or any(r.id in [STATE['roles'].get(n) for n in STAFF] for r in member.roles)


def panel(title, body):
    e = discord.Embed(title=title, description=body, color=0xF01424)
    e.set_footer(text='TGN RACING • TARRAGONA, CATALUNYA • BUILT TO COMPETE.')
    return e


async def reply(i, content):
    if i.response.is_done():
        await i.followup.send(content, ephemeral=True)
    else:
        await i.response.send_message(content, ephemeral=True)


def logo_bytes():
    embedded = BASE / 'logo_base64.txt'
    if embedded.exists():
        return base64.b64decode(embedded.read_text().strip())
    for name in ['logo-original.jpeg', 'logo-original.jpg', 'logo-original.png']:
        path = BASE / name
        if path.exists():
            return path.read_bytes()
    return None


def overwrites(guild, access, read=False):
    # Solo se conceden los permisos básicos que necesita la conversación.
    # No se conceden manage_messages/manage_channels ni poderes de moderación.
    public = access == 'public'
    permissions = {
        guild.default_role: discord.PermissionOverwrite(view_channel=public, send_messages=public and not read),
        guild.me: discord.PermissionOverwrite(view_channel=True, send_messages=True, read_message_history=True, embed_links=True, attach_files=True),
    }
    names = STAFF if access == 'staff' else TEAM if access == 'team' else ['Comunidad'] if access == 'community' else []
    for name in set(names + STAFF):
        obj = role(guild, name)
        if obj:
            permissions[obj] = discord.PermissionOverwrite(view_channel=True, send_messages=(name in STAFF or not read), read_message_history=True)
    return permissions


class AccessView(discord.ui.View):
    def __init__(self):
        super().__init__(timeout=None)

    @discord.ui.button(label='Acepto las normas · Entrar al paddock', style=discord.ButtonStyle.danger, custom_id='tgn:community:v1')
    async def accept(self, i: discord.Interaction, button: discord.ui.Button):
        if not authorized(i):
            return await reply(i, 'Servidor no autorizado.')
        await i.response.defer(ephemeral=True)
        obj = role(i.guild, 'Comunidad')
        if not obj:
            return await reply(i, 'Primero hay que completar /instalar.')
        try:
            await i.user.add_roles(obj, reason='Aceptación de normas TGN')
            await reply(i, 'Acceso a Comunidad habilitado. ¡Bienvenido al paddock!')
        except discord.HTTPException:
            await reply(i, 'No puedo asignar Comunidad. Revisa Gestionar roles y coloca el rol del bot por encima de Comunidad.')


class ApplicationModal(discord.ui.Modal, title='Solicitud · TGN Racing'):
    alias = discord.ui.TextInput(label='Alias de piloto', max_length=70)
    experience = discord.ui.TextInput(label='Simulador y experiencia', style=discord.TextStyle.paragraph, max_length=700)
    availability = discord.ui.TextInput(label='Disponibilidad y zona horaria', max_length=250)
    objectives = discord.ui.TextInput(label='Objetivos y qué puedes aportar', style=discord.TextStyle.paragraph, max_length=900)
    lfm = discord.ui.TextInput(label='Perfil LFM (opcional)', required=False, max_length=250)

    async def on_submit(self, i: discord.Interaction):
        await i.response.defer(ephemeral=True)
        if not authorized(i):
            return await reply(i, 'Servidor no autorizado.')
        async with TICKET_LOCK:
            uid = str(i.user.id)
            old = STATE['tickets'].get(uid, {})
            existing = i.guild.get_channel(old.get('channel', 0))
            if existing:
                return await reply(i, f'Ya tienes una solicitud: {existing.mention}. Staff puede reabrirla si está cerrada.')
            cat = i.guild.get_channel(STATE['categories'].get('07 ━ SOLICITUDES · PRIVADO', 0))
            if not cat:
                return await reply(i, 'Todavía no está instalada la categoría de solicitudes.')
            if len(cat.channels) >= 45:
                return await reply(i, 'La bandeja está llena. Contacta con el staff.')
            ch = None
            try:
                perms = overwrites(i.guild, 'staff')
                perms[i.user] = discord.PermissionOverwrite(view_channel=True, send_messages=True, read_message_history=True, attach_files=True)
                ch = await i.guild.create_text_channel(f'solicitud-{i.user.id}', category=cat, overwrites=perms, reason='Solicitud voluntaria TGN')
                STATE['tickets'][uid] = {'channel': ch.id, 'closed': False}
                save()
                e = panel('SOLICITUD · TGN RACING', f'Solicitante: {i.user.mention}\nLa incorporación requiere valoración del equipo.')
                for name, value in [('Alias', self.alias.value), ('Experiencia', self.experience.value), ('Disponibilidad', self.availability.value), ('Objetivos', self.objectives.value), ('LFM (no verificado)', self.lfm.value or 'No facilitado')]:
                    e.add_field(name=name, value=value, inline=False)
                await ch.send(embed=e)
                await reply(i, f'Solicitud creada: {ch.mention}. Visible para ti, staff y administradores.')
            except discord.HTTPException:
                LOG.exception('Error en solicitud')
                await reply(i, f'No se pudo completar la publicación. {"El canal fue creado; avisa al staff." if ch else "Avisa al staff para revisar permisos."}')


class RecruitmentView(discord.ui.View):
    def __init__(self):
        super().__init__(timeout=None)

    @discord.ui.button(label='Presentar solicitud privada', style=discord.ButtonStyle.danger, custom_id='tgn:apply:v1')
    async def apply(self, i: discord.Interaction, button: discord.ui.Button):
        if not authorized(i):
            return await reply(i, 'Servidor no autorizado.')
        await i.response.send_modal(ApplicationModal())


async def publish(guild, key, title, body, view=None, logo=False):
    ch = channel(guild, key)
    if not ch:
        return
    old = STATE['messages'].get(key)
    if old:
        try:
            await ch.fetch_message(old)
            return
        except discord.NotFound:
            pass
    e = panel(title, body)
    kwargs = {'embed': e}
    if view:
        kwargs['view'] = view
    original = logo_bytes() if logo else None
    if original:
        kwargs['file'] = discord.File(io.BytesIO(original), filename='tgn-logo.jpeg')
        e.set_thumbnail(url='attachment://tgn-logo.jpeg')
    message = await ch.send(**kwargs)
    STATE['messages'][key] = message.id
    save()


class InstallFailure(Exception):
    pass


async def install(guild):
    stage = 'comprobar permisos'
    try:
        me = await guild.fetch_member(client.user.id)
        required = ['manage_channels', 'manage_roles', 'view_channel', 'send_messages', 'read_message_history', 'embed_links', 'attach_files']
        missing = [p for p in required if not getattr(me.guild_permissions, p)]
        if missing:
            raise RuntimeError('Faltan permisos del bot: ' + ', '.join(missing))
        ROLES.update({r.id: r for r in await guild.fetch_roles()})
        stage = 'crear roles pendientes'
        for name, color in CONFIG['roles']:
            if not role(guild, name):
                LOG.info('Creando rol: %s', name)
                obj = await guild.create_role(name=name, color=discord.Color(color), permissions=discord.Permissions.none(), hoist=name in TEAM, mentionable=False, reason='Instalación TGN confirmada')
                STATE['roles'][name] = obj.id
                ROLES[obj.id] = obj
                save()
        # No hay ninguna llamada para mover roles ni asignar Fundador.
        stage = 'comprobar jerarquía de roles'
        ROLES.update({r.id: r for r in await guild.fetch_roles()})
        bot_roles = [ROLES.get(r.id, r) for r in me.roles]
        top = max(bot_roles)
        blocked = [name for name, _ in CONFIG['roles'] if role(guild, name) >= top]
        if blocked:
            raise RuntimeError('Coloca el rol del bot por encima de: ' + ', '.join(blocked) + '. Guarda y repite /instalar.')
        for spec in CONFIG['categories']:
            stage = f'categoría: {spec["name"]}'
            cat = guild.get_channel(STATE['categories'].get(spec['name'], 0))
            if not cat:
                LOG.info('Creando %s', stage)
                cat = await guild.create_category(spec['name'], overwrites=overwrites(guild, spec['access']), reason='Instalación TGN confirmada')
                STATE['categories'][spec['name']] = cat.id
                save()
            for name, mode in spec['text']:
                stage = f'canal de texto: {name}'
                if not channel(guild, name):
                    LOG.info('Creando %s', stage)
                    ch = await guild.create_text_channel(name, category=cat, overwrites=overwrites(guild, spec['access'], mode=='read'), slowmode_delay=5 if mode=='chat' else 0, reason='Instalación TGN confirmada')
                    STATE['channels'][name] = ch.id
                    save()
            for name in spec.get('voice', []):
                stage = f'canal de voz: {name}'
                if not channel(guild, name):
                    LOG.info('Creando %s', stage)
                    ch = await guild.create_voice_channel(name, category=cat, overwrites=overwrites(guild, spec['access']), reason='Instalación TGN confirmada')
                    STATE['channels'][name] = ch.id
                    save()
        messages = [
            ('bienvenida', 'TGN RACING · BUILT TO COMPETE.', 'Desde Tarragona, competimos con precisión, determinación y espíritu de equipo.\n\nFundado por HAF.\n\nLee #normativa y acepta las normas en #elige-tu-acceso para entrar al paddock.\n\nEscudería virtual independiente. Sin afiliación oficial con LFM.', None, True),
            ('normativa', 'NORMATIVA · RESPETO EN PISTA Y FUERA DE ELLA', '1. Respeta a todas las personas. Sin acoso, discriminación ni amenazas.\n2. Competición limpia: sin trampas ni exploits.\n3. No publiques datos personales, contraseñas, tokens ni contenido ilegal.\n4. Sin spam, publicidad no autorizada ni menciones masivas.\n5. Usa el canal correspondiente. No difundas recursos privados del equipo.\n6. Resuelve discrepancias con respeto y pruebas.\n7. Sigue las indicaciones del staff.\n\nAceptar las normas no verifica identidad ni concede acceso a pilotos.', None, False),
            ('elige-tu-acceso', 'TU SITIO EN EL PADDOCK', 'Pulsa para aceptar las normas y recibir Comunidad. No concede acceso a pilotos ni dirección.', AccessView(), False),
            ('reclutamiento', '¿TIENES LO NECESARIO PARA COMPETIR?', 'Presenta tu experiencia, disponibilidad y objetivos. La solicitud será visible para ti, staff y administradores. No envíes datos sensibles. El equipo confirmará requisitos y posibles pruebas. No se garantiza una plaza.', RecruitmentView(), False),
            ('preguntas-frecuentes', 'ANTES DE LA PRIMERA VUELTA', '¿Cómo accedo? Acepta las normas en el panel.\n¿Cómo soy piloto? Presenta una solicitud y espera la valoración del equipo.\n¿Hay resultados? Solo se publicarán datos confirmados.\n¿LFM? No hay integración automática.\n¿Mis datos? Las solicitudes se conservan en Discord; pide al staff su eliminación cuando corresponda.', None, False),
            ('anuncios', 'COMUNICADOS OFICIALES', 'Aquí se publicarán novedades confirmadas del equipo.', None, False),
            ('calendario', 'PRÓXIMA SALIDA', 'Próximamente anunciaremos nuestras próximas carreras. Fechas y horarios pendientes de confirmación.', None, False),
            ('resultados', 'RESULTADOS VERIFICADOS', 'Todavía no hay resultados publicados.\nFormato: fecha, serie, circuito, categoría, piloto, posición, mejor vuelta e incidentes.', None, False),
            ('noticias-lfm', 'LOW FUEL MOTORSPORT', 'Noticias contrastadas y enlaces reales. Sin sincronización automática ni afiliación oficial.\nPlataforma general: https://lowfuelmotorsport.com/', None, False),
            ('briefing', 'BRIEFING DE CARRERA', 'Completar con datos confirmados: serie, circuito, fecha, zona horaria, pilotos, reglamento, duración, combustible, neumáticos y estrategia.', None, False),
            ('disponibilidad', 'DISPONIBILIDAD DE PILOTOS', 'Indica evento, disponibilidad y zona horaria. No publiques información personal sensible.', None, False),
            ('staff', 'GESTIÓN DEL EQUIPO', 'El orden de roles se establece manualmente. El bot debe estar por encima de todos los roles TGN. No se asigna Fundador automáticamente: hazlo manualmente a la cuenta correcta.\n/piloto gestiona Piloto TGN (administradores). /cerrar cierra una solicitud sin borrar mensajes.\nNo hay AutoMod ni registro exhaustivo automático. Revisa permisos y retención de solicitudes.', None, False),
        ]
        for key, title, body, view, logo in messages:
            stage = f'publicar panel: {key}'
            LOG.info('%s', stage)
            await publish(guild, key, title, body, view, logo)
    except Exception as exc:
        LOG.exception('Instalación detenida en: %s', stage)
        detail = f'Discord {exc.status}, código {exc.code}' if isinstance(exc, discord.HTTPException) else str(exc)
        raise InstallFailure(f'Paso: {stage}\nDetalle: {detail}\nSe conserva lo ya creado. No borres state.json.') from exc


class ConfirmInstall(discord.ui.View):
    def __init__(self, user_id):
        super().__init__(timeout=120)
        self.user_id = user_id

    @discord.ui.button(label='Confirmar instalación de TGN Racing', style=discord.ButtonStyle.danger)
    async def confirm(self, i: discord.Interaction, button: discord.ui.Button):
        if not authorized(i) or i.user.id != self.user_id or not i.user.guild_permissions.administrator:
            return await reply(i, 'Solo el administrador que abrió el plan puede confirmarlo.')
        await i.response.defer(ephemeral=True, thinking=True)
        button.disabled = True
        await i.edit_original_response(view=self)
        if INSTALL_LOCK.locked():
            return await reply(i, 'Ya hay una instalación en curso. Espera a que termine.')
        async with INSTALL_LOCK:
            try:
                await install(i.guild)
                await reply(i, 'Instalación completada. No se han movido roles ni asignado Fundador automáticamente. Revisa los accesos con una cuenta normal antes de invitar a otras personas. /identidad permite aplicar nombre y logo con confirmación.')
            except InstallFailure as exc:
                await reply(i, 'Instalación incompleta.\n' + str(exc))


class TGNClient(discord.Client):
    def __init__(self):
        super().__init__(intents=discord.Intents.default(), allowed_mentions=discord.AllowedMentions.none())
        self.tree = app_commands.CommandTree(self)

    async def setup_hook(self):
        self.add_view(AccessView())
        self.add_view(RecruitmentView())
        target = discord.Object(id=GUILD_ID)
        self.tree.copy_global_to(guild=target)
        await self.tree.sync(guild=target)

    async def on_ready(self):
        LOG.info('BOT REVISADO TGN v2 conectado. Servidor: %s. Ejecuta /instalar.', GUILD_ID)


client = TGNClient()


@client.tree.command(name='instalar', description='Revisar y confirmar instalación TGN sin mover roles')
@app_commands.default_permissions(administrator=True)
@app_commands.checks.has_permissions(administrator=True)
async def instalar(i: discord.Interaction):
    if not authorized(i):
        return await reply(i, 'Servidor no autorizado.')
    ntext = sum(len(c['text']) for c in CONFIG['categories'])
    nvoice = sum(len(c.get('voice', [])) for c in CONFIG['categories'])
    body = f'Servidor: {i.guild.name} ({i.guild.id})\n\nHasta {len(CONFIG["roles"])} roles, {len(CONFIG["categories"])} categorías, {ntext} canales de texto y {nvoice} de voz, con paneles de normas, acceso y solicitudes.\n\nSe reutilizan los IDs de state.json. No se borra contenido, NO se mueven roles y NO se asigna Fundador automáticamente. No se modifican permisos de canales ya registrados. Puede haber una instalación parcial si Discord rechaza alguna operación.\n\nEl nombre y el icono se cambian únicamente con /identidad confirmar:True.'
    await i.response.send_message(embed=panel('PLAN DE INSTALACIÓN · V2', body), view=ConfirmInstall(i.user.id), ephemeral=True)


@client.tree.command(name='identidad', description='Cambiar nombre e icono solo con confirmación explícita')
@app_commands.default_permissions(administrator=True)
@app_commands.checks.has_permissions(administrator=True)
async def identidad(i: discord.Interaction, confirmar: bool = False):
    if not authorized(i):
        return await reply(i, 'Servidor no autorizado.')
    name = CONFIG.get('server_name', 'TGN Racing | Simracing')
    if not confirmar:
        return await reply(i, f'Se sustituirán el nombre por «{name}» y el icono por el logo original. Autoriza con /identidad confirmar:True. Discord muestra el icono con su máscara circular.')
    original = logo_bytes()
    if not original:
        return await reply(i, 'No encuentro logo_base64.txt ni logo-original.jpeg. No se ha cambiado nada.')
    await i.response.defer(ephemeral=True)
    await i.guild.edit(name=name, icon=original, reason=f'Identidad confirmada por {i.user.id}')
    await reply(i, 'Nombre e icono actualizados.')


@client.tree.command(name='piloto', description='Asignar o retirar Piloto TGN; solo administradores')
@app_commands.default_permissions(administrator=True)
@app_commands.checks.has_permissions(administrator=True)
async def piloto(i: discord.Interaction, miembro: discord.Member, activar: bool):
    if not authorized(i):
        return await reply(i, 'Servidor no autorizado.')
    obj = role(i.guild, 'Piloto TGN')
    if not obj:
        return await reply(i, 'Primero completa /instalar.')
    await i.response.defer(ephemeral=True)
    if activar:
        await miembro.add_roles(obj, reason=f'Alta autorizada por {i.user.id}')
    else:
        await miembro.remove_roles(obj, reason=f'Baja autorizada por {i.user.id}')
    await reply(i, 'Rol actualizado. Otros roles pueden seguir dando acceso; revísalos por separado.')


@client.tree.command(name='cerrar', description='Cerrar solicitud actual sin eliminarla')
async def cerrar(i: discord.Interaction):
    if not authorized(i) or not staff(i.user):
        return await reply(i, 'Solo staff o administradores.')
    found = next(((uid, t) for uid, t in STATE['tickets'].items() if t.get('channel') == i.channel_id), None)
    if not found:
        return await reply(i, 'Utiliza este comando dentro de una solicitud creada por el bot.')
    await i.response.defer(ephemeral=True)
    uid, ticket = found
    try:
        member = await i.guild.fetch_member(int(uid))
    except discord.NotFound:
        member = None
    if member:
        await i.channel.set_permissions(member, view_channel=True, send_messages=False, read_message_history=True, reason='Solicitud cerrada por staff')
    ticket['closed'] = True
    save()
    await i.channel.send(embed=panel('SOLICITUD CERRADA', 'Se conserva la conversación sin exportarla. El staff puede reabrirla o eliminarla manualmente cuando corresponda.'))
    await reply(i, 'Solicitud cerrada. Los administradores conservan su acceso administrativo.')


@client.tree.error
async def command_error(i: discord.Interaction, error):
    if isinstance(error, app_commands.MissingPermissions):
        return await reply(i, 'Este comando requiere permisos de administrador.')
    original = getattr(error, 'original', error)
    LOG.error('Error de comando', exc_info=(type(original), original, original.__traceback__))
    detail = f'Discord {original.status}, código {original.code}' if isinstance(original, discord.HTTPException) else type(original).__name__
    await reply(i, f'No se pudo completar la acción: {detail}. Revisa el último error de la consola.')


if __name__ == '__main__':
    if not TOKEN or not GUILD_ID:
        raise SystemExit('Completa DISCORD_TOKEN y GUILD_ID en .env. No compartas el token.')
    client.run(TOKEN, log_level=logging.INFO)
