# GEODATA-AUTO-INGEST

A repo-friendly automation package for preparing and auto-ingesting geospatial datasets into GeoManager/Climweb.

This repo now supports both major raster workflows cleanly:

- **GeoTIFF workflow**
  - CHIRPS v3 Africa dekadal rainfall → Lesotho clip → GeoManager auto-ingest
  - LMS or other local GeoTIFF sources → optional clip → GeoManager auto-ingest
- **NetCDF workflow**
  - Local or remote `.nc` files → optional variable validation → GeoManager auto-ingest

The structure is meant to grow. You can add more source-specific ingestors later, for example LMS forecast rasters, NDVI/VHI rasters, JRC WSI rasters, or sector-specific NetCDF products.

---

## Repo layout

```text
GEODATA-AUTO-INGEST/
├── pyproject.toml
├── README.md
├── env/
│   ├── chirps_v3_africa.env.example
│   ├── lms_geotiff_template.env.example
│   └── netcdf_template.env.example
├── scripts/
│   ├── run_chirps_v3_africa.sh
│   ├── run_lms_geotiff_template.sh
│   └── run_netcdf_template.sh
└── src/
    └── geodata_auto_ingest/
        ├── __init__.py
        ├── common/
        │   ├── __init__.py
        │   ├── chirps.py
        │   ├── ingest.py
        │   ├── logging_utils.py
        │   └── shell.py
        └── sources/
            ├── __init__.py
            ├── chirps_v3_africa.py
            ├── lms_geotiff_template.py
            └── netcdf_template.py
```

---

## What GeoManager expects

GeoManager treats GeoTIFF and NetCDF differently.

### GeoTIFF
GeoManager auto-ingest for GeoTIFF depends on the filename ending with an ISO UTC timestamp in this form:

```text
YYYY-MM-DDTHH:MM:SS.sssZ
```

Example:

```text
chirps-v3.0.2026.02.3-LSO_2026-02-21T00:00:00.000Z.tif
```

That is why the GeoTIFF ingestors in this repo create staged filenames with that suffix.

### NetCDF
GeoManager supports `.nc` files and extracts time from the file itself. The layer in GeoManager must have:

- **Auto ingest from directory** enabled
- **Data variable for netCDF data auto ingest** set to the correct variable name

This repo does not rename NetCDF files with timestamps because GeoManager reads time from inside the file.

The GeoManager README says:
- netCDF time is automatically extracted from the file
- GeoTIFF time is normally assigned manually
- raster auto-ingest supports `.tif` and `.nc`

---

## Logging and rotation

Every ingestor uses rotating logs.

Each env file defines:

- `LOG_DIR`
- `LOG_FILE`
- `LOG_MAX_BYTES`
- `LOG_BACKUP_COUNT`

Default behavior:
- 1 active log file
- rotate at 5 MB
- keep 5 backups

That is enough to avoid uncontrolled log growth.

---

## Prerequisites

- Docker installed
- `climweb` container running
- GeoManager auto-ingest already wired in `climweb-docker`
- the target raster layer already configured with:
  - **Auto ingest from directory** = enabled
  - **Use custom directory name** = enabled
  - the matching custom directory name
- for GeoTIFF clipping: `gdalwarp` available on the host
- for optional local NetCDF variable validation: install the extra:
  ```bash
  pip install ".[netcdf-validation]"
  ```

---

## GeoTIFF workflow 1: CHIRPS v3 Africa

### Env file

```bash
cp env/chirps_v3_africa.env.example env/chirps_v3_africa.env
```

Edit it to match your host paths.

### Run latest dekad

```bash
./scripts/run_chirps_v3_africa.sh
```

### Run one explicit dekad

```bash
export PYTHONPATH="$PWD/src"
python3 -m geodata_auto_ingest.sources.chirps_v3_africa \
  --ymd 2026 02 3 \
  --base-url https://data.chc.ucsb.edu/products/CHIRPS/v3.0/dekads/africa/tifs/ \
  --version-prefix chirps-v3.0 \
  --boundary /data/chirps-manual/raw/lesotho_boundary_admin0.geojson \
  --work-dir /data/geodata-auto-ingest/work/chirps-v3-africa \
  --ingest-dir /opt/climweb-docker/climweb/geomanager-data/chirps-dekadal-lesotho \
  --layer-dir-name chirps-dekadal-lesotho \
  --container climweb \
  --log-dir /var/log/geodata-auto-ingest \
  --overwrite
```

What it does:
1. download one CHIRPS `.tif.gz`
2. unzip it
3. clip to Lesotho using GDAL
4. rename to the ISO UTC suffix GeoManager expects
5. copy into the layer ingest directory
6. run `process_geomanager_layer_directory`

---

## GeoTIFF workflow 2: LMS/local GeoTIFF template

This is the clean pattern for any local GeoTIFF source.

### Env file

```bash
cp env/lms_geotiff_template.env.example env/lms_geotiff_template.env
```

### Run it

```bash
./scripts/run_lms_geotiff_template.sh
```

What it does:
1. take a local GeoTIFF
2. optionally clip it using a boundary
3. stage it with the required ISO UTC suffix
4. copy it into the layer ingest directory
5. run GeoManager ingest

This is the correct place to plug in future LMS raster products.

---

## NetCDF workflow

### Env file

```bash
cp env/netcdf_template.env.example env/netcdf_template.env
```

### Run it

```bash
./scripts/run_netcdf_template.sh
```

### Explicit example

```bash
export PYTHONPATH="$PWD/src"
python3 -m geodata_auto_ingest.sources.netcdf_template \
  --src-file /data/upstream/example.nc \
  --staged-name example-forecast-timeseries \
  --work-dir /data/geodata-auto-ingest/work/netcdf-template \
  --ingest-dir /opt/climweb-docker/climweb/geomanager-data/example-forecast-timeseries \
  --layer-dir-name example-forecast-timeseries \
  --container climweb \
  --expected-variable precip \
  --clip-in-geomanager \
  --log-dir /var/log/geodata-auto-ingest \
  --overwrite
```

What it does:
1. copy or download a NetCDF file
2. optionally validate that the expected variable exists locally
3. stage the file into the layer ingest directory
4. run GeoManager ingest
5. let GeoManager extract timestamps from the file itself

### Important NetCDF note

For NetCDF, the GeoManager layer UI must have the correct **Data variable for netCDF data auto ingest** set. The local `--expected-variable` in this repo is only a pre-check. GeoManager still performs its own validation during ingest.

---

## Cron examples

### CHIRPS dekadal

```cron
30 6 10,20,28 * * /usr/bin/bash /opt/GEODATA-AUTO-INGEST/scripts/run_chirps_v3_africa.sh >> /var/log/geodata_auto_ingest_chirps_cron.log 2>&1
```

### LMS local GeoTIFF

```cron
15 * * * * /usr/bin/bash /opt/GEODATA-AUTO-INGEST/scripts/run_lms_geotiff_template.sh >> /var/log/geodata_auto_ingest_lms_cron.log 2>&1
```

### NetCDF

```cron
45 * * * * /usr/bin/bash /opt/GEODATA-AUTO-INGEST/scripts/run_netcdf_template.sh >> /var/log/geodata_auto_ingest_netcdf_cron.log 2>&1
```

Adjust schedules to the real availability of your upstream data.

---

## Recommended GitHub commit sequence

A clean first sequence would be:

1. initial repo scaffold
2. CHIRPS v3 GeoTIFF ingestor
3. rotating logging
4. LMS GeoTIFF template
5. NetCDF ingestor
6. docs and env examples

---

## Limits and sharp edges

- GeoTIFF ingest will fail if the staged filename does not end with the required ISO UTC timestamp.
- NetCDF ingest depends on the target layer's NetCDF data variable being configured correctly in GeoManager.
- This repo does not fetch or parse every source-specific format automatically; each new source should get its own module under `sources/`.
- NetCDF clipping is not done on the host in this repo. Use `--clip-in-geomanager` if you want GeoManager to apply boundary clipping during ingest.

---

## References used for this repo design

This structure follows GeoManager’s documented support for:
- GeoTIFF and NetCDF uploads
- time extraction from NetCDF
- directory-based raster auto-ingest
- GeoTIFF filename-based timestamp parsing during ingest

Repository references:
- GeoManager README
- `geomanager/utils/ingest.py`

Those are the parts that dictate why the GeoTIFF and NetCDF workflows cannot be treated identically.
