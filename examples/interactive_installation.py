from pathlib import Path
from typing import TYPE_CHECKING, Callable, Optional

import archinstall
from archinstall import Installer, profile, SysInfo, disk, menu, models, locale, info, debug

if TYPE_CHECKING:
	_: Callable[[str], str]


def ask_user_questions() -> None:
	"""
	Función para solicitar al usuario que responda varias preguntas sobre la configuración del sistema.
	"""
	global_menu = archinstall.GlobalMenu(data_store=archinstall.arguments)

	# Habilitar la selección del idioma de Archinstall
	global_menu.enable('archinstall-language')

	# Configurar la región para descargar paquetes durante la instalación
	global_menu.enable('mirror_config')

	# Configurar la localización
	global_menu.enable('locale_config')

	# Configurar el disco (obligatorio)
	global_menu.enable('disk_config', mandatory=True)

	# Especificar opciones de cifrado de disco
	global_menu.enable('disk_encryption')

	# Preguntar qué gestor de arranque usar (solo si estamos en modo UEFI, de lo contrario, se usará GRUB por defecto)
	global_menu.enable('bootloader')

	# Configurar el intercambio (swap)
	global_menu.enable('swap')

	# Obtener el nombre de host para la máquina
	global_menu.enable('hostname')

	# Preguntar por una contraseña de root (opcional, pero requiere un superusuario si se omite)
	global_menu.enable('!root-password', mandatory=True)

	# Configurar usuarios (obligatorio)
	global_menu.enable('!users', mandatory=True)

	# Preguntar por perfiles específicos de Archinstall (como entornos de escritorio, etc.)
	global_menu.enable('profile_config')

	# Preguntar sobre la selección del servidor de audio si no se ha configurado uno
	global_menu.enable('audio_config')

	# Preguntar por el kernel preferido (obligatorio)
	global_menu.enable('kernels', mandatory=True)

	# Configurar paquetes adicionales
	global_menu.enable('packages')

	if archinstall.arguments.get('advanced', False):
		# Habilitar descargas paralelas
		global_menu.enable('parallel downloads')

	# Preguntar o llamar a la función auxiliar que solicita al usuario que configure una red opcionalmente
	global_menu.enable('network_config')

	# Configurar la zona horaria
	global_menu.enable('timezone')

	# Configurar la sincronización de tiempo (NTP)
	global_menu.enable('ntp')

	# Configurar repositorios adicionales
	global_menu.enable('additional-repositories')

	# Separador visual en el menú
	global_menu.enable('__separator__')

	# Guardar configuración
	global_menu.enable('save_config')

	# Iniciar instalación
	global_menu.enable('install')

	# Abortar instalación
	global_menu.enable('abort')

	global_menu.run()


def perform_installation(mountpoint: Path) -> None:
	"""
	Realiza los pasos de instalación en un dispositivo de bloque.
	El único requisito es que los dispositivos de bloque estén formateados y configurados antes de ingresar a esta función.
	"""
	info('Starting installation...')
	disk_config: disk.DiskLayoutConfiguration = archinstall.arguments['disk_config']

	# Recuperar la lista de repositorios adicionales y establecer valores booleanos apropiados
	enable_testing = 'testing' in archinstall.arguments.get('additional-repositories', [])
	enable_multilib = 'multilib' in archinstall.arguments.get('additional-repositories', [])
	locale_config: locale.LocaleConfiguration = archinstall.arguments['locale_config']
	disk_encryption: disk.DiskEncryption = archinstall.arguments.get('disk_encryption', None)

	with Installer(
		mountpoint,
		disk_config,
		disk_encryption=disk_encryption,
		kernels=archinstall.arguments.get('kernels', ['linux'])
	) as installation:
		# Montar todas las unidades en el punto de montaje deseado
		if disk_config.config_type != disk.DiskLayoutType.Pre_mount:
			installation.mount_ordered_layout()

		installation.sanity_check()

		if disk_config.config_type != disk.DiskLayoutType.Pre_mount:
			if disk_encryption and disk_encryption.encryption_type != disk.EncryptionType.NoEncryption:
				# Generar archivos de clave de cifrado para los dispositivos luks montados
				installation.generate_key_files()

		if mirror_config := archinstall.arguments.get('mirror_config', None):
			installation.set_mirrors(mirror_config)

		installation.minimal_installation(
			testing=enable_testing,
			multilib=enable_multilib,
			hostname=archinstall.arguments.get('hostname', 'archlinux'),
			locale_config=locale_config
		)

		if mirror_config := archinstall.arguments.get('mirror_config', None):
			installation.set_mirrors(mirror_config, on_target=True)

		if archinstall.arguments.get('swap'):
			installation.setup_swap('zram')

		if archinstall.arguments.get("bootloader") == models.Bootloader.Grub and SysInfo.has_uefi():
			installation.add_additional_packages("grub")

		installation.add_bootloader(archinstall.arguments["bootloader"])

		# Si el usuario seleccionó copiar la configuración de red actual del ISO
		# Realizar una copia de la configuración
		network_config = archinstall.arguments.get('network_config', None)

		if network_config:
			network_config.install_network_config(
				installation,
				archinstall.arguments.get('profile_config', None)
			)

		if users := archinstall.arguments.get('!users', None):
			installation.create_users(users)

		audio_config: Optional[models.AudioConfiguration] = archinstall.arguments.get('audio_config', None)
		if audio_config:
			audio_config.install_audio_config(installation)
		else:
			info("No se instalará ningún servidor de audio")

		if archinstall.arguments.get('packages', None) and archinstall.arguments.get('packages', None)[0] != '':
			installation.add_additional_packages(archinstall.arguments.get('packages', []))

		if profile_config := archinstall.arguments.get('profile_config', None):
			profile.profile_handler.install_profile_config(installation, profile_config)

		if timezone := archinstall.arguments.get('timezone', None):
			installation.set_timezone(timezone)

		if archinstall.arguments.get('ntp', False):
			installation.activate_time_synchronization()

		if archinstall.accessibility_tools_in_use():
			installation.enable_espeakup()

		if (root_pw := archinstall.arguments.get('!root-password', None)) and len(root_pw):
			installation.user_set_pw('root', root_pw)

		if profile_config := archinstall.arguments.get('profile_config', None):
			profile_config.profile.post_install(installation)

		# Si el usuario proporcionó una lista de servicios para habilitar, pasar la lista a la función enable_service.
		# Tenga en cuenta que aunque se llama enable_service, en realidad puede tomar una lista de servicios e iterarla.
		if archinstall.arguments.get('services', None):
			installation.enable_service(archinstall.arguments.get('services', []))

		# Si el usuario proporcionó comandos personalizados para ejecutar después de la instalación, ejecutarlos ahora.
		if archinstall.arguments.get('custom-commands', None):
			archinstall.run_custom_user_commands(archinstall.arguments['custom-commands'], installation)

		installation.genfstab()

		info("Para consejos post-instalación, vea https://wiki.archlinux.org/index.php/Installation_guide#Post-installation")

		if not archinstall.arguments.get('silent'):
			prompt = str(_('¿Le gustaría chrootear en la instalación recién creada y realizar la configuración post-instalación?'))
			choice = menu.Menu(prompt, menu.Menu.yes_no(), default_option=menu.Menu.yes()).run()
			if choice.value == menu.Menu.yes():
				try:
					installation.drop_to_shell()
				except Exception:
					pass

	debug(f"Estados del disco después de la instalación: {disk.disk_layouts()}")


ask_user_questions()

fs_handler = disk.FilesystemHandler(
	archinstall.arguments['disk_config'],
	archinstall.arguments.get('disk_encryption', None)
)

fs_handler.perform_filesystem_operations()

perform_installation(archinstall.storage.get('MOUNT_POINT', Path('/mnt')))
