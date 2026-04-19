# biosforge — TODO / Roadmap

## Visión

**The ultimate open source BIOS tool.** Un workbench donde el técnico carga archivos, 
ve una descomposición detallada de cada uno, y elige interactivamente qué regiones y 
módulos tomar de cada fuente para construir su imagen flashable.

---

## v0.1.0 — MVP (COMPLETADO)

- [x] Flash Descriptor parser (Intel IFD)
- [x] ME region parser ($FPT, particiones, versión)
- [x] Region extraction y manipulation
- [x] Image builder (combinar regiones → flashable)
- [x] External tools manager (registro de herramientas)
- [x] HP vendor parser (softpaq .bin con header 0x220)
- [x] CLI: info, build, tools
- [x] GUI básica: cargar archivos, ver regiones, build
- [x] Repo GitHub: Teleloco/biosforge

---

## v0.2.0 — Herramientas integradas + Análisis profundo

### Herramientas externas en `tools/` (TODAS dentro del proyecto)

```
tools/
├── MEAnalyzer/          # platomav/MEAnalyzer (Python, BSD-2) ← CLONADO
├── BIOSUtilities/       # platomav/BIOSUtilities (Python, BSD-2) ← CLONADO
├── MCExtractor/         # platomav/MCExtractor (Python, BSD-2) ← CLONADO
├── me_cleaner/          # corna/me_cleaner (Python, GPL-3) ← CLONADO
├── uefi-firmware-parser/# theopolis/uefi-firmware-parser (Python) ← CLONADO
├── chipsec/             # chipsec/chipsec (Python, GPL-2) ← CLONADO
├── UEFITool/            # LongSoft/UEFITool (C++, BSD-2) → binarios pre-built
│   ├── UEFIExtract.exe
│   └── UEFIFind.exe
├── ifdtool/             # coreboot ifdtool (C, GPL-2) → compilar o pre-built
└── flashrom/            # flashrom (C, GPL-2) → binario pre-built
```

- [x] Script setup_tools.py para clonar herramientas Python
- [x] Actualizar external_tools.py → buscar SOLO en `tools/`
- [x] Base de datos CPUID → plataforma (cpuid_db.py, ~75 entries Intel+AMD)
- [x] Métodos parsed para MEA y MCExtractor (run_meanalyzer_parsed, run_mcextractor_parsed)
- [ ] Integrar MEA: ejecutar automáticamente al cargar dump/ME
- [ ] Integrar MCExtractor: extraer info de microcode (CPUID, versión, fecha)
- [ ] Integrar BIOSUtilities: extracción de cápsulas multi-vendor
- [ ] Integrar uefi-firmware-parser: listar UEFI FV volumes y módulos
- [ ] Integrar me_cleaner: opción para limpiar ME desde GUI (subprocess, GPL)
- [ ] Integrar ifdtool: info detallada del descriptor (subprocess, GPL)
- [x] Descargar binarios pre-built de UEFIExtract/UEFIFind en setup_tools.py
- [ ] Agregar flashrom como herramienta opcional para flash directo

### Análisis profundo: image_analyzer.py (NUEVO)

Al cargar CUALQUIER archivo, analizar y mostrar:

- [ ] Tipo de imagen: full dump, vendor BIOS, ME-only, unknown
- [ ] Flash Descriptor detallado (regiones, permisos, masters)
- [ ] ME state: **clean** (never initialized) vs **configured** (MFS tiene datos) vs **partial**
- [ ] ME versión/SKU/generación (via MEA)
- [ ] SMBIOS/DMI: fabricante, modelo, serial (buscar strings en BIOS region)
- [ ] Microcode: CPUID, versión, fecha (buscar headers Intel MC)
- [ ] Checksums: MD5/SHA256 del archivo y de cada región
- [ ] Data fill por región (% no-FF)
- [ ] Clasificar cada región como usable/no-usable con razón explicada
- [ ] Vendor detection automática (HP, Dell, Lenovo, etc.)

---

## v0.3.0 — GUI interactiva: tabla de regiones con selección

### Concepto: Region Map interactivo

```
                 │ [1] Dump         │ [2] Vendor BIOS  │ [3] Clean ME    │
─────────────────┼──────────────────┼──────────────────┼─────────────────│
Descriptor (4KB) │ (x) OK           │ ( ) n/a          │ ( ) OK          │
ME Region (7MB)  │ ( ) configured   │ ( ) partial 2MB  │ (x) clean       │
BIOS Region (9MB)│ ( ) v01.28.00    │ (x) v01.31.00    │ ( ) v01.29.00   │
GbE              │ (x) disabled     │     —            │     —           │
```

- [ ] Tabla con columnas por archivo cargado
- [ ] Radio buttons por fila (una fuente por región)
- [ ] Cada celda muestra: estado, versión, usabilidad
- [ ] Click en celda → panel de detalles con info completa
- [ ] Defaults inteligentes: Desc→dump, ME→clean, BIOS→vendor
- [ ] Validación de compatibilidad en tiempo real
- [ ] Status bar: ✓ Compatible / ⚠ Warnings / ✗ Error
- [ ] Bloquear Build si hay errores de compatibilidad

### Validación de compatibilidad entre archivos

- [ ] Flash layout (tamaños de regiones deben coincidir)
- [ ] ME generation (major version compatible)
- [ ] Microcode CPUID (mismo procesador)
- [ ] SMBIOS vendor/product (mismo equipo)
- [ ] Mostrar diff visual cuando hay diferencias

---

## v0.4.0 — Vendors adicionales

- [x] Dell: parser PFS (via BIOSUtilities DellPfsExtract)
- [ ] Lenovo: parser (via BIOSUtilities, Insyde iFlash)
- [ ] Asus: parser CAP
- [ ] Acer: parser cápsulas
- [ ] AMI Aptio: parser (via BIOSUtilities AmiPfatExtract)
- [ ] Insyde H2O: parser (via BIOSUtilities InsydeIfdExtract)
- [ ] Phoenix: parser TDK (via BIOSUtilities PhoenixTdkExtract)
- [ ] Apple EFI: parser (via BIOSUtilities Apple*)
- [ ] Auto-detección: probar todos los parsers hasta que uno matchee

---

## v0.5.0 — Edición avanzada

- [ ] Editor DMI/SMBIOS: cambiar serial, UUID, fabricante, modelo
- [ ] Editor de NVRAM/UEFI variables
- [ ] Reemplazo de módulos UEFI individuales (DXE drivers, PEI modules)
- [ ] Inserción/extracción de microcódigo actualizado
- [ ] Parcheo de ME: cambiar configuración sin reemplazar toda la región
- [ ] Visor hexadecimal integrado para regiones individuales
- [ ] Diff visual entre dos regiones del mismo tipo

---

## v0.6.0 — Migración a coreboot

- [ ] Base de datos de boards soportados por coreboot (parsear su repo)
- [ ] Detección automática del board desde dump (DMI/SMBIOS strings)
- [ ] Si board soportado → ofrecer migración a coreboot
- [ ] Wizard de configuración coreboot (payload: SeaBIOS/TianoCore, opciones)
- [ ] Integrar coreboot toolchain para compilar imagen
- [ ] Generar imagen coreboot flashable con descriptor/ME del dump original
- [ ] Documentación de proceso de migración

---

## v1.0.0 — Herramientas propias que no existen

- [ ] **biosforge-dump**: herramienta propia para leer/escribir SPI flash (CH341a, FT2232)
      sin depender de flashrom — interfaz más amigable, auto-detect de chip
- [ ] **biosforge-me-analyzer**: análisis de ME propio en Python puro (sin depender de MEA)
      con detección de state clean/configured/corrupted
- [ ] **biosforge-uefi-parser**: parser UEFI propio más completo que uefi-firmware-parser
      con soporte para edición in-place de módulos
- [ ] **biosforge-patcher**: sistema de patches reutilizables — definir patches como
      recetas (JSON) que se aplican automáticamente (ej: "deshabilitar whitelist WiFi",
      "unlock advanced menu", "bypass password")
- [ ] **biosforge-db**: base de datos comunitaria de BIOS — versiones conocidas por modelo,
      hashes verificados, compatibilidad de ME, patches disponibles
- [ ] **Platform auto-detect**: sin cargar nada manualmente, conectar programador,
      leer chip, auto-detectar plataforma, sugerir acciones

---

## Futuro / Ideas

- [ ] Plugin system para vendors custom
- [ ] Integración con programadores SPI desde la GUI (flashrom backend)
- [ ] Remote flash: conectar al programador por red (Raspberry Pi como puente)
- [ ] Batch processing: procesar múltiples dumps con la misma receta
- [ ] Web UI alternativa (para uso desde el banco de reparación)
- [ ] Exportar reportes PDF de análisis
- [ ] Soporte AMD PSP (equivalente a Intel ME para AMD)
- [ ] Soporte ARM TrustZone firmware
- [ ] Community patches repository (GitHub-based)
