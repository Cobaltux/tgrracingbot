# TGN RACING | DISCORD COMPLETO

Paquete de instalación para un servidor de Discord de TGN Racing. Fundado por HAF. Negro, rojo y amarillo; mensajes técnicos y estructura deportiva, sin inventar pilotos, resultados ni afiliación oficial con LFM.

IMPORTANTE: esto es un instalador funcional de la estructura, no un servidor ya creado ni una invitación. Debes crear un servidor vacío en tu cuenta, autorizar tu propio bot y confirmar /instalar dentro de Discord. No usa tu contraseña ni un token de usuario (selfbot).

## Qué configura

7 categorías, 25 canales de texto, 6 de voz y 7 roles:

01 STARTING GRID (público, lectura)
- bienvenida
- normativa
- anuncios
- elige-tu-acceso: botón persistente para aceptar normas y obtener Comunidad

02 PADDOCK (Comunidad)
- general, presentaciones, simracing, clips-y-capturas, hardware-y-setups
- Voz: Paddock General y Paddock Simracing

03 RACE CONTROL (Comunidad)
- calendario, resultados, noticias-lfm (lectura, staff publica)
- directos (conversación)

04 TGN RACING PRIVADO (equipo y staff)
- briefing (lectura), entrenamientos, telemetria-y-setups, estrategia, debriefing, disponibilidad
- Voz: Box TGN 01, Box TGN 02, Ingeniería Radio

05 ENTRA EN TGN (público, lectura)
- reclutamiento: botón de solicitud y formulario modal
- preguntas-frecuentes

06 DIRECCIÓN PRIVADO (staff)
- staff, gestion-pilotos, planificacion, registro-bot
- Voz: Dirección Reunión

07 SOLICITUDES PRIVADO
- Cada formulario genera un canal privado para solicitante y staff.
- No permite varias solicitudes simultáneas de la misma persona.
- /cerrar bloquea la escritura del solicitante, pero no elimina los mensajes.
- La eliminación y reapertura las hace staff manualmente. Una solicitud cerrada conservada impide abrir otra hasta eliminar su canal o reabrirla.

## Roles y permisos

Orden: Fundador > Dirección > Staff > Ingeniería > Piloto TGN > Piloto reserva > Comunidad.

No se otorga Administrator a ningún rol. El propietario que confirma la instalación recibe el rol descriptivo Fundador. Esto no identifica automáticamente al propietario como HAF; HAF figura como fundador en los mensajes. Si la cuenta de HAF es otra, el propietario debe asignarle el rol manualmente.

Fundador/Dirección/Staff: acceso a dirección, solicitudes y zona del equipo; pueden escribir en los canales de solo lectura. /cerrar comprueba esos roles. No reciben poderes de ban o expulsión automáticamente. Los administradores existentes conservan su acceso administrativo de Discord.

Ingeniería/Piloto TGN/Piloto reserva: zona privada del equipo, pero no dirección ni solicitudes de otros usuarios.

Comunidad: paddock y race control. El botón público SOLO puede asignar Comunidad.

Sin roles: bienvenida, normas, anuncios, acceso y reclutamiento. Nadie obtiene acceso deportivo solo por aceptar normas.

Al conceder un rol de equipo, el miembro también debe aceptar las normas para obtener Comunidad y ver el paddock.

## Instalación paso a paso

Requisitos: Python 3.10 o posterior y un ordenador o servidor donde puedas ejecutar el bot. El paquete no incluye alojamiento de pago ni requiere suscripción para el contenido básico.

1. Crea un servidor NUEVO y vacío desde tu cuenta de Discord. Usa un servidor de prueba antes de invitar a gente.
2. En el Discord Developer Portal crea una aplicación y su bot.
3. Copia .env.example como .env y completa DISCORD_TOKEN con el token de TU BOT. Nunca uses tu contraseña, un token de usuario ni lo pegues en chats.
4. Activa el modo desarrollador de Discord; copia el ID del servidor y completa GUILD_ID en .env.
5. En la instalación/OAuth2 selecciona los scopes bot y applications.commands. Invita el bot a ese servidor.
6. Concede los permisos del bot: Manage Server, Manage Channels, Manage Roles, View Channels, Send Messages, Read Message History, Embed Links, Attach Files. No necesita Administrator. Su rol debe estar por encima de todos los roles TGN que gestionará.
7. No actives Message Content, Server Members ni Presence Intent. Este proyecto usa interacciones y no necesita esos intents privilegiados.
8. Abre una terminal en la carpeta y ejecuta:

    python -m venv .venv

Windows:

    .venv\Scripts\activate

macOS/Linux:

    source .venv/bin/activate

Después:

    python -m pip install -r requirements.txt
    python bot.py

9. En Discord ejecuta /instalar como administrador. Revisa el plan y pulsa el botón de confirmación. La creación puede tardar mientras Discord limita las peticiones.
10. Para aplicar el nombre y el escudo al servidor: /identidad muestra qué va a cambiar. Usa /identidad confirmar:True únicamente si aceptas sustituir el nombre y el icono actuales.
11. Revisa los permisos y prueba con una cuenta normal antes de invitar al resto.

Si Windows usa el comando py en lugar de python, sustitúyelo en las instrucciones. INICIAR-WINDOWS.bat arranca con python una vez instaladas las dependencias; no instala Python ni dependencias por sí mismo.

## Logotipo

Se incluye el archivo original sin redibujar, modificar colores ni deformar. También se incluyen sus mismos bytes en logo_base64.txt: el bot lo adjunta a la bienvenida desde memoria, sin rutas web ni servicios externos. Para el icono del servidor se utiliza el archivo original completo. Discord muestra el icono con su máscara circular y tamaño de interfaz; el bot no recorta ni cambia el contenido del archivo.

El problema de la web anterior no se ha diagnosticado ni reparado aquí: este es un proyecto independiente. El logo del servidor no depende de aquella web.

## Comandos

/instalar — Administrador. Plan y confirmación explícita. Crea solo los objetos que falten según state.json. No elimina contenido ni cambia permisos de objetos ya registrados.
/identidad confirmar:False — Administrador. Muestra el cambio propuesto de nombre e icono.
/identidad confirmar:True — Administrador. Aplica nombre e icono.
/piloto miembro:USUARIO activar:True — Administrador. Asigna Piloto TGN.
/piloto miembro:USUARIO activar:False — Administrador. Retira únicamente Piloto TGN; revisa otros roles que puedan mantener el acceso.
/cerrar — Staff o administrador. Dentro de un canal de solicitud creado por el bot, bloquea su escritura. No borra mensajes ni crea transcripciones.

Los roles Dirección, Staff, Ingeniería y Piloto reserva se asignan manualmente desde Discord para evitar menús de escalado de permisos.

## Persistencia y reinicios

Conserva .env y state.json en un disco persistente. No ejecutes dos copias simultáneas con el mismo token y estado. Haz copias de seguridad privadas.

state.json contiene IDs de roles, canales, mensajes y usuarios con solicitudes; NO contiene tokens ni transcripciones. Aun así es información que debe protegerse. Si lo borras, el instalador no puede reconocer lo creado y puede duplicar objetos. No adopta canales ajenos solo por coincidir en nombre.

El servidor, sus canales, roles y mensajes continúan existiendo aunque apagues el bot. Los botones y comandos requieren que esté conectado. Las vistas se registran de nuevo al arrancar para que los botones antiguos vuelvan a funcionar. Un PC apagado no puede atender solicitudes; usa un proceso supervisado en un equipo o alojamiento que controles si lo necesitas permanentemente disponible.

## Personalizar

config.json permite cambiar nombres de roles, colores, categorías y canales ANTES de instalar. Mantén los roles y nombres funcionales esperados por bot.py si no vas a adaptar también su lógica: Comunidad, Piloto TGN y categorías de solicitudes se usan en código.

Después de la instalación puedes editar los mensajes desde Discord (el propietario no puede editar mensajes del bot como si fueran propios; utiliza cambios en bot.py y elimina el mensaje del panel antes de repetir /instalar para publicarlo actualizado). Repetir /instalar no sobrescribe paneles existentes ni reaplica permisos de canales ya registrados: conserva tus ajustes manuales.

Las fechas, resultados y noticias se publican manualmente por staff. No hay conexión automática con LFM. config.json contiene un campo lfm_url reservado; esta entrega NO lo utiliza para generar un perfil. Publica el enlace real manualmente cuando esté confirmado. No se ha inventado ninguna cuenta.

## Moderación y privacidad

Hay normas, separación por roles, canales privados y slowmode de 5 segundos en chats generales. No se instala AutoMod, antiraid, filtro de palabras, captcha ni registro exhaustivo de mensajes. Configura los controles nativos de Discord y revisa el nivel de verificación antes de abrir el servidor. registro-bot es un canal preparado para uso del equipo; el bot escribe errores en su terminal, no registra cada acción en ese canal.

Las solicitudes quedan en mensajes de Discord accesibles al solicitante, staff y administradores. No hay envío a terceros ni exportación automática. Define una política de retención y elimina solicitudes cuando dejen de ser necesarias. No solicites documentos de identidad, contraseñas ni datos sensibles. El botón de aceptar normas no equivale a verificación de identidad ni a un consentimiento legal universal.

En un servidor nuevo los permisos privados están aislados por overwrites. Los administradores siempre pueden acceder. Los roles personalizados, bots o permisos previos pueden cambiar el resultado: de ahí la recomendación de instalar en un servidor nuevo y revisarlo con una cuenta de prueba.

## Qué se ha verificado

- Sintaxis Python válida mediante ast.parse.
- Configuración JSON válida; 7 roles, 7 categorías, 25 textos, 6 voces.
- Decodificación del logo incrustado idéntica al adjunto original.
- Comprobación estática de scopes de funciones y estructura de archivos.

No se ha ejecutado contra Discord: no tengo tu token ni acceso a tu cuenta y no lo debes compartir aquí. No se han probado permisos reales, límites del servidor ni interacción con otros bots. Requiere instalar las dependencias y hacer la prueba final en tu servidor. Si una instalación falla, consulta el error, corrige permisos y repite sin borrar state.json; puede haber quedado parcialmente creada.
