import Link from "next/link";
import HeroArt from "../components/HeroArt";
const entries = [
  [
    "simulation",
    "Simulation",
    "Rotating shallow water",
    "Set an initial condition and follow waves, vorticity and conservation.",
  ],
  [
    "earth",
    "Earth",
    "Observed ocean currents",
    "Trace drifting particles through historical Arabian Sea currents.",
  ],
  [
    "neural",
    "Neural",
    "Learned dynamics",
    "Compare CNN and Fourier operator forecasts with the numerical reference.",
  ],
  [
    "hpc",
    "HPC",
    "Computational scaling",
    "Inspect the measured cost and accuracy of CPU and GPU rollouts.",
  ],
];
export default function Home() {
  return (
    <>
      <section className="hero">
        <div className="herocopy">
          <div className="eyebrow">
            <i /> Computational geophysics
          </div>
          <h1>
            Fluid dynamics
            <br />
            <em>in motion.</em>
          </h1>
          <p>
            Experiment with rotating fluids, trace the observed ocean, and
            measure how well neural operators predict its dynamics.
          </p>
          <Link className="button primary" href="/simulation">
            Open simulation <span aria-hidden>↗</span>
          </Link>
        </div>
        <HeroArt />
      </section>
      <section id="labs" className="directory">
        <div className="directory-head">
          <h2>Research laboratories</h2>
          <Link href="/research">Research &amp; verification ↗</Link>
        </div>
        <div className="lablinks">
          {entries.map(([key, name, sub, desc]) => (
            <Link href={"/" + key} key={key}>
              <div className={"glyph " + key} aria-hidden>
                <i />
                <i />
                <i />
              </div>
              <small>{sub}</small>
              <h3>
                {name} <span aria-hidden>↗</span>
              </h3>
              <p>{desc}</p>
            </Link>
          ))}
        </div>
      </section>
    </>
  );
}
