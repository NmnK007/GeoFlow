# From the equations to one solver step

## Model and conserved state

Assume constant density, hydrostatic vertical pressure and depth-uniform horizontal velocity over a level bottom. With x east, y north, total depth h=H+η and material derivative D/Dt=∂t+u∂x+v∂y, the depth-integrated equations are

```text
∂t h + ∂x(hu) + ∂y(hv) = 0
Du/Dt = −g ∂x h + f v
Dv/Dt = −g ∂y h − f u
```

Multiply the u equation by h. By the product rule, ∂t(hu)+∂x(hu²)+∂y(huv) equals h Du/Dt plus u times the continuity equation. The latter vanishes. Moving gh ∂x h to the flux gives ∂x(gh²/2). The same argument for v gives the northward pressure flux. Set Q=(h,mx,my)=(h,hu,hv). The result is ∂t Q + ∂x F + ∂y G = S with

```text
F = (mx, mx u + gh²/2, mx v)
G = (my, my u, my v + gh²/2)
S = (0, f my, −f mx)
```

Each float64 cell stores three approximate cell averages in `Q[:,j,i]`. Smooth initial profiles and analytical references use centre samples. Cell (j,i) has centre ((i+½)Δx,(j+½)Δy), Δx=Lx/nx and Δy=Ly/ny. Thickness is in metres, velocity in m/s and momentum per horizontal area per density in m²/s.

## Interfaces and conservation

Integrate over a cell and divide by its area. The divergence theorem turns divergence into outward face fluxes. Approximate the eastward interface flux from neighbouring cell values with

```text
F̂(L,R) = (F(L)+F(R))/2 − a (R−L)/2
a = max(|uL|+√(g hL), |uR|+√(g hR))
```

The jump term damps unresolved jumps with a speed that bounds the normal wave speeds. The northward interface uses G and v. Equal states recover the analytical flux. See `physics.flux` and `physics.rusanov`. For periodic edges `boundaries.faces` computes the seam once and repeats its value at the opposite end. At walls `boundaries.ghost` flips only normal momentum. Equal ghost/interior depth and opposite normal transport give zero numerical mass flux.

For a concrete step consider a 3-column by 2-row grid with Δx=2 m, Δy=1 m, g=1 m/s², f=0. Start both rows at depths [1,2,1] m with zero velocity and use periodic boundaries. At the first internal x face the mass flux is −√2/2 m²/s. At the next face it is +√2/2. Both y flux differences vanish. With Δt=0.1 s the centre column changes by −0.1√2/2 m and each outside column gains 0.1√2/4 m. The summed depth change is zero. Momentum also evolves through the pressure flux. For every component `solver.trial` applies

```text
Q* = Q − (Δt/Δx)(F̂east−F̂west) − (Δt/Δy)(Ĝnorth−Ĝsouth).
```

The same interior flux enters adjacent cells with opposite signs. Summing the mass equation cancels all interior contributions. Walls can exert pressure forces on momentum.

## Rotation and time control

Latitude resolves to f=2Ω sin(φ), Ω=7.292115×10⁻⁵ rad/s, with degrees converted to radians. Any numeric `f_override_s_inv`, including zero, wins. Solving the constant-coefficient source ODE gives

```text
mx' = cos(fΔt) mx* + sin(fΔt) my*
my' = cos(fΔt) my* − sin(fΔt) mx*.
```

With positive f an eastward parcel initially accelerates south. This orthogonal transformation preserves squared momentum of the isolated source. `physics.rotate` uses both old components. Transport followed by rotation is first-order Lie splitting.

The CFL rate is max(|u|+√gh)/Δx + max(|v|+√gh)/Δy. Both directions contribute to an unsplit update. Divide C by this rate, with default C=0.4 and 0<C≤0.5. Cap the result at the remaining time to the next output and, for nonzero f, at 0.1/|f| to resolve coupled dynamics. Output targets are built from integer sample indices and include the final time once. `solver.advance` halves an invalid trial interval and starts again from the accepted state. Eight retries are allowed by default. Finite values and h above the configured floor (default 10⁻⁸ m) are required throughout. An exhausted retry or step budget raises an error.

## Diagnostics and resources

Volume V=ΔxΔy Σh is proportional to mass. Report |V−V₀|/V₀. Energy per unit density E=ΔxΔy Σ[h(u²+v²)/2+g(h−H)²/2] removes constant and conserved linear terms from gravitational energy. Its units are m⁵/s². Record E−E₀ and, for nonzero E₀, (E−E₀)/E₀. A blank relative-energy CSV cell means undefined. Sampled dt and CFL describe the last accepted step leading to that output. Step and rejection counts are cumulative. Runtime is elapsed solver time in seconds.

Relative vorticity is ζ=∂x v−∂y u and PV is (ζ+f)/h. `diagnostics.vorticity` differences opposite neighbours over two spacings, wrapping periodic fields and extending tangential velocity evenly across walls. Differentiating a numerically diffused velocity attenuates small vortices. Wall estimates use the chosen ghost extension.

Work per step is O(nx ny). The retained float64 fields require exactly 24 nt nx ny bytes. Grid-dependent working arrays are budgeted separately at an estimated 640 bytes per cell. These checks precede field allocation. Configurable limits also bound grid dimensions, frames, retries and accepted steps. Memory estimates exclude Python, plotting and compression overhead.
