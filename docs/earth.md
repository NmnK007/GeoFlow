# Earth laboratory

Earth advects passive tracers in prescribed velocity fields. GLORYS provides assimilative model output, DUACS supplies satellite-derived geostrophic currents, and NOAA GDP provides independently processed buoy trajectories. The numerical shallow-water experiments have their own inputs, equations and verification suite.

## Obtain a regional case

The worked case uses 55–73° E, 8–20° N and four daily fields from 00:00 UTC July 1 through July 4, 2020. Run the fetch and analyze commands in the [quickstart](../README.md). Fetch requests only four grid variables and seven drifter columns. In this run the grid response was 466,100 bytes and the drifter CSV 13,260 bytes. Raw responses, exact request URLs, retrieval timestamps and SHA-256 hashes are saved under `data/arabian-july-2020`. Use a new output directory for each analysis.

| Source | Variables and physical interpretation | Acquisition |
|---|---|---|
| GLORYS12V1, GLOBAL_MULTIYEAR_PHY_001_030 | uo, vo are eastward and northward model currents at a depth level, zos is sea-surface height. Daily dataset cmems_mod_glo_phy_my_0.083deg_P1D-m. | Official subsetter or a local CF NetCDF export. [Product and licence](https://data.marine.copernicus.eu/product/GLOBAL_MULTIYEAR_PHY_001_030/description) · [Variable definitions](https://documentation.marine.copernicus.eu/PUM/CMEMS-GLO-PUM-001-030.pdf) |
| DUACS, SEALEVEL_GLO_PHY_L4_MY_008_047 | ugos and vgos are absolute surface geostrophic currents, adt is absolute dynamic topography, sla is sea-level anomaly. Current catalogue daily dataset cmems_obs-sl_glo_phy-ssh_my_allsat-l4-duacs-0.125deg_P1D. | The measured case uses NOAA's historical 0.25° delayed-time archive SEA_SURFACE_HEIGHT_2020_v3. Archive and current catalogue grids differ. [Product and licence](https://data.marine.copernicus.eu/product/SEALEVEL_GLO_PHY_L4_MY_008_047/description) · [Archive metadata](https://erddap.aoml.noaa.gov/hdb/erddap/info/SEA_SURFACE_HEIGHT_2020_v3/index.html) |
| NOAA GDP drifter_hourly_qc | Interpolated, quality-controlled hourly positions, east and north velocities ve and vn in m/s, trajectory ID and drogue loss date. | Public ERDDAP subset. GDP v2.01, Elipot et al., DOI 10.25921/x46c-3620, CC BY 4.0. [Provider metadata and attribution](https://erddap.aoml.noaa.gov/gdp/erddap/info/drifter_hourly_qc/index.html) |

The worked case contains modified Copernicus Marine Service information and uses observations made available by the NOAA Global Drifter Program. Copernicus product DOIs are 10.48670/moi-00021 (GLORYS) and 10.48670/moi-00148 (DUACS product family). Preserve file-level attribution, provider terms, source version, DOI and access date when publishing. For third-party local files, an unspecified licence requires checking with the source. [Copernicus citation guidance](https://help.marine.copernicus.eu/en/articles/4444611-citing-copernicus-marine-products-and-services)

For direct Copernicus access, install the optional official Toolbox separately, run `copernicusmarine login` interactively, and leave credentials in the tool's user-managed location outside this repo. GeoFlow passes region, dates and variable names to the installed CLI. For example, `python -m geoflow.earth.cli subset --product glorys --case "Bay of Bengal" --out data/bay.nc` requests only the upper metre. The same command accepts `duacs`. Alternatively obtain NetCDF via the provider website and use local import. The authenticated download path was not exercised in this release. [Toolbox documentation](https://toolbox-docs.marine.copernicus.eu/en/stable/)

`earth.cases.CASES` defines Arabian Sea, Bay of Bengal, Somali Current, winter monsoon contrast, mesoscale eddies and surface transport windows. Change region and interval using `--box WEST EAST SOUTH NORTH --start ... --end ...`; specify an available level using `--depth`. The Arabian Sea and winter cases share spatial bounds for a seasonal comparison. Acquire matching files first. The worked study makes no seasonal inference from three elapsed days.

## CF processing and geographic mathematics

`earth.data.canonical` decodes CF time, packing and fill values through xarray, sorts and subsets rectilinear coordinates and selects a single depth (default shallowest available). Longitude becomes continuous eastward from the requested west boundary, including across ±180°. Regions span at most 180° and exclude the poles. Velocities and elevations are normalized to m/s and metres. Declared CF sea/land binary masks and missing values exclude invalid water. Curvilinear grids, rotated vector bases and non-Gregorian calendars require separate treatment. Selected fields have a projected 256 MiB cap. `import_region` uses a local file fingerprint plus exact selection parameters as its cache key.

With longitude λ and latitude φ in **radians**, use dx=R cosφ dλ and dy=R dφ. The map uses a local equirectangular display with the central latitude as its standard parallel. Distances for scoring use the spherical haversine formula and a wrapped longitude difference, with R=6,371,000 m.

`earth.diagnostics.fields` constructs the east/north covariant velocity gradient. Let ∂x=(R cosφ)⁻¹∂λ and ∂y=R⁻¹∂φ. The four entries are A=∂x u−v tanφ/R, B=∂y u, C=∂x v+u tanφ/R, D=∂y v. Use centred differences on the physical coordinate axes. A derivative needs valid neighboring samples and a valid centre; edge derivatives without a complete centred stencil are undefined.

- Relative vorticity ζ=C−B, absolute vorticity ζ+2Ω sinφ, divergence A+D, normal strain A−D, shear strain B+C (s⁻¹). Okubo–Weiss W=(A−D)²+(B+C)²−ζ² (s⁻²).
- Speed is √(u²+v²); direction is the bearing **towards** which water flows, clockwise from true north, undefined at rest. Specific kinetic energy is (u²+v²)/2. Instantaneous EKE uses half the sum of squared departures from the arithmetic mean of valid paired current samples at each point over the selected interval (m²/s²). An irregularly sampled window weights each sample equally. A four-day mean describes departures within that window.
- Geostrophic components are −g ∂yη/f and g ∂xη/f. ADT yields absolute geostrophic estimates; SLA yields anomaly velocities. The 3° equatorial exclusion avoids small-f division. Recomputing gradients from gridded heights can differ from a provider's filtered velocities.

## Particles and eddy candidates

`earth.tracking.Current` interpolates east/north velocity bilinearly in space and linearly between time slices. `track` solves dλ/dt=u/(R cosφ), dφ/dt=v/R using signed Euler or RK4 steps. End times are hit exactly. Ensembles use explicit release locations. There is no random walk, windage or subgrid coast model.

Each accepted chord and each RK stage chord is partitioned wherever it crosses a longitude, latitude or time grid face. In each open piece the interpolation footprint is fixed. A nonfinite contributing corner or domain exit terminates the track at its last accepted position, with a recorded reason. This prevents skipping a masked **grid** island on a long step. Subgrid coastlines, velocity changes between source samples and unresolved curvature remain physical limitations. Reduce the step and compare solutions. Times in particle exports are seconds relative to the first source field.

`earth.eddies.candidates` finds four-connected cells with W below a threshold, sufficient |SLA|, and matching rotation and height signs. In either hemisphere a cyclonic candidate has fζ>0 and negative SLA. The equatorial band is excluded. Area uses R² Δλ (sinφN−sinφS), centres use area weights on the continuous regional branch, and equivalent radius is √(area/π). On the first real field, raising the required OW magnitude from 0 to 10⁻¹¹ to 5×10⁻¹¹ s⁻² reduced the count from 49 to 23 to 6 (|SLA|≥2 cm, ≥4 cells). These are threshold-dependent connected regions. Closed material boundaries, persistence and comparison against an eddy catalogue remain unverified.

## Numerical verification

Offline tests use manufactured fields. A uniform flow tests distance, signs and reverse integration. A linearly varying current tests time interpolation. A masked strip tests rejection of intermediate crossings. For an analytical angular vortex, exact rotation isolates ODE error from gridded interpolation. With a 10,000 s integration and steps 1000, 500 and 250 s, the last refinement gave orders **1.0083** (Euler) and **3.99998** (RK4). The remaining RK4 angular error was 1.63×10⁻⁹ degrees in the test coordinate norm. This order applies to smooth prescribed velocities; it is not an accuracy estimate for a daily satellite product.

Further tests cover antimeridian subsetting, exact level selection, distance, CF/NetCDF roundtrips, unit conversion, masks, spherical tensor terms, geostrophic signs, eddy classification in both hemispheres, scoring and coverage, and Streamlit interactions. Run `python -m pytest -q` after installing all extras. The numerical solver's independent `geoflow verify` command remains available.

## Observational validation

Use each GDP ID returned by the bounded query exactly once, starting at its first observation during current coverage. Require contiguous hourly positions for the requested horizon and a finite initial observed velocity. Report exclusions and terminations. Compare prescribed-current RK4 tracks (900 s step), a stationary release, and a constant *observed initial* east/north velocity following a rhumb line. Score great-circle separations at hours 1–24, exclude the guaranteed zero error at release, and count valid samples for each method and horizon. Validation exports include the complete observed and comparison coordinates.

| July 1–2, two releases | Mean separation (km) | RMS separation (km) | Mean 24 h separation (km) |
|---|---:|---:|---:|
| Satellite-derived currents, RK4 | 5.108 | 5.742 | 8.110 |
| Stationary | 5.778 | 7.024 | 10.233 |
| Constant initial observed velocity | 5.403 | 6.590 | 10.344 |

Both tracks completed, all 48 noninitial hourly pairs per method were valid, and zero IDs were excluded. ID 300234065411660 had lost its drogue on June 11, 2020. Its final RK4/stationary separations were 7.857/13.566 km. ID 300234065411840 retained its drogue at release (reported loss January 20, 2021). Its final RK4/stationary separations were 8.364/6.900 km. The aggregate advantage did not hold on both tracks.

Daily surface geostrophic currents omit direct wind-driven and other ageostrophic transport. An attached GDP drogue samples subsurface motion, typically around 15 m; a detached float responds differently to wind and waves. The case matches position and time but has no exact dynamical-depth match. GDP positions and initial velocities are themselves processed estimates. Regional selection may truncate tracks crossing a query boundary. Two trajectories and one release date do not establish predictive skill or uncertainty intervals.

## Reproduce and extend

The export contains the selected region and diagnostics as NetCDF, candidate and particle CSVs, map, exact import settings and source attributes. Drifter runs add a matched-observation CSV, separation plot and a JSON report with per-horizon counts, errors and termination rate. `python -m geoflow.earth.cli analyze --fixture --out outputs/my-fixture` exercises offline export with an explicitly synthetic vortex. In the Earth UI, use **Integrate particles** for one or more release pairs, select a time before the release for a backward trajectory, then **Export Earth analysis**.

The CLI also accepts repeated `--release LON LAT` pairs, `--method rk4` or `euler`, `--dt` in seconds and `--end-index`. Releases start at the selected field index. The analysis JSON records particle configuration separately from validation settings.

As a first exercise, compute the spherical vorticity of a constant eastward current by hand and compare with the corresponding test. Next halve the integration step in the Arabian Sea case and compare the change against the observed kilometre-scale error. Before any future release that relies on observational skill, expand to independent dates, regions and drifter IDs, stratify by drogue status, compare depth-matched reanalysis and quantify sampling uncertainty.
