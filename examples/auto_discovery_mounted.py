from pathlib import Path
from archinstall import disk

# Directorio raíz donde se montarán los dispositivos
root_mount_dir = Path('/mnt/archinstall')

# Detectar modificaciones de dispositivos pre-montados
mods = disk.device_handler.detect_pre_mounted_mods(root_mount_dir)

# Configurar la disposición del disco basada en las modificaciones detectadas
disk_config = disk.DiskLayoutConfiguration(
	disk.DiskLayoutType.Pre_mount,
	device_modifications=mods,
)

# Log de las modificaciones detectadas para análisis posterior
print(f"Modificaciones detectadas: {mods}")
