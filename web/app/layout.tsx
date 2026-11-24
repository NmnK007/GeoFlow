import type { Metadata } from "next";
import type { ReactNode } from "react";
import Link from "next/link";
import "./style.css";
import ModeProvider from "../components/Mode";
export const metadata: Metadata = {
  title: "GeoFlow · Fluid Dynamics Laboratory",
  description:
    "Explore rotating fluids, ocean observations and the cost of predicting them.",
};
export default function Layout({ children }: { children: ReactNode }) {
  return (
    <html lang="en">
      <body>
        <a className="skip" href="#main">
          Skip to content
        </a>
        <header>
          <Link href="/" className="brand">
            <span className="emblem" aria-hidden="true">
              ≋
            </span>
            GeoFlow
          </Link>
          <nav aria-label="Laboratories">
            {["Simulation", "Earth", "Neural", "HPC", "Research"].map((n) => (
              <Link key={n} href={"/" + n.toLowerCase()}>
                {n}
              </Link>
            ))}
          </nav>
        </header>
        <main id="main"><ModeProvider>{children}</ModeProvider></main>
        <footer>
          GeoFlow <span>Geophysical fluid dynamics laboratory</span>
        </footer>
      </body>
    </html>
  );
}
