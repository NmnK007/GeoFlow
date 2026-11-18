# v0.1 baseline limits

For the current release see [v0.2 model and experiment limits](dynamics.md).

GeoFlow v0.1 models a single homogeneous hydrostatic layer of positive depth on a local plane. Periodic edges recirculate disturbances. Free-slip walls reflect waves. Constant f describes a chosen latitude locally. The setup excludes wind, friction, vertical stratification, bathymetry and wetting or drying.

First-order Rusanov transport diffuses waves and vortices. A fine grid can reproduce wave phase accurately while still underestimating amplitude. Lie splitting introduces transport–rotation coupling error. Neither mechanical energy, potential vorticity nor general geostrophic balance is exactly preserved by the coupled scheme. The verification suite covers analytical solutions and idealized experiments. Real-ocean validation would require observations and an appropriate physical model.

Before considering an approved later release, use the saved convergence results as regression evidence and quantify amplitude damping and balance error for any proposed scheme. Beta-plane dynamics, improved reconstruction, topography, real-data ingestion, ML and accelerated backends belong to separate release decisions.
