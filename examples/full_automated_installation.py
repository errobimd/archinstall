from pathlib import Path
from archinstall import Installer, profile, disk, models
from archinstall.default_profiles.minimal import MinimalProfile

# Tipo de sistema de archivos a utilizar
fs_type = disk.FilesystemType('ext4')
device_path = Path('/dev/sda')

# Obtener el dispositivo de disco físico
device = disk.device_handler.get_device(device_path)

if not device:
	raise ValueError('No se encontró el dispositivo para la ruta dada')

# Crear una nueva modificación para el dispositivo específico
device_modification = disk.DeviceModification(device, wipe=True)

# Crear una nueva partición de arranque
boot_partition = disk.PartitionModification(
	status=disk.ModificationStatus.Create,
	type=disk.PartitionType.Primary,
	start=disk.Size(1, disk.Unit.MiB, device.device_info.sector_size),
	length=disk.Size(512, disk.Unit.MiB, device.device_info.sector_size),
	mountpoint=Path('/boot'),
	fs_type=disk.FilesystemType.Fat32,
	flags=[disk.PartitionFlag.Boot]
)
device_modification.add_partition(boot_partition)

# Crear una partición raíz
root_partition = disk.PartitionModification(
	status=disk.ModificationStatus.Create,
	type=disk.PartitionType.Primary,
	start=disk.Size(513, disk.Unit.MiB, device.device_info.sector_size),
	length=disk.Size(20, disk.Unit.GiB, device.device_info.sector_size),
	mountpoint=None,
	fs_type=fs_type,
	mount_options=[],
)
device_modification.add_partition(root_partition)

# Calcular el inicio y la longitud de la partición home
start_home = root_partition.length
length_home = device.device_info.total_size - start_home

# Crear una nueva partición home
home_partition = disk.PartitionModification(
	status=disk.ModificationStatus.Create,
	type=disk.PartitionType.Primary,
	start=start_home,
	length=length_home,
	mountpoint=Path('/home'),
	fs_type=fs_type,
	mount_options=[]
)
device_modification.add_partition(home_partition)

# Configuración de la disposición del disco
disk_config = disk.DiskLayoutConfiguration(
	config_type=disk.DiskLayoutType.Default,
	device_modifications=[device_modification]
)

# Configuración de cifrado de disco (Opcional)
disk_encryption = disk.DiskEncryption(
	encryption_password="enc_password",
	encryption_type=disk.EncryptionType.Luks,
	partitions=[home_partition],
	hsm_device=None
)

# Iniciar el manejador de archivos con la configuración del disco y la configuración opcional de cifrado de disco
fs_handler = disk.FilesystemHandler(disk_config, disk_encryption)

# Realizar todas las operaciones de archivos
# ADVERTENCIA: esto potencialmente formateará el sistema de archivos y eliminará todos los datos
fs_handler.perform_filesystem_operations(show_countdown=False)

# Punto de montaje para la instalación
mountpoint = Path('/tmp')

# Iniciar la instalación
with Installer(
	mountpoint,
	disk_config,
	disk_encryption=disk_encryption,
	kernels=['linux']
) as installation:
	installation.mount_ordered_layout()
	installation.minimal_installation(hostname='minimal-arch')
	installation.add_additional_packages(['nano', 'wget', 'git'])

# Opcionalmente, instalar un perfil de elección.
# En este caso, instalamos un perfil mínimo que está vacío
profile_config = profile.ProfileConfiguration(MinimalProfile())
profile.profile_handler.install_profile_config(installation, profile_config)

# Crear un usuario
user = models.User('archinstall', 'password', True)
installation.create_users(user)

# Log de la instalación para análisis posterior
print("Instalación completada con éxito.")
