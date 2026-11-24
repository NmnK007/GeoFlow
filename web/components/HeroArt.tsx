"use client";
import { Component, useEffect, useRef, useState } from "react";
import dynamic from "next/dynamic";
const Vortex = dynamic(() => import("./Vortex"), { ssr: false });
class Fallback extends Component<
  { children: React.ReactNode },
  { failed: boolean }
> {
  state = { failed: false };
  static getDerivedStateFromError() {
    return { failed: true };
  }
  render() {
    return this.state.failed ? null : this.props.children;
  }
}
export default function HeroArt() {
  const host = useRef<HTMLDivElement>(null),
    [active, enable] = useState(false),
    [small, compact] = useState(false),
    [paused, pause] = useState(false);
  useEffect(() => {
    const pref = matchMedia("(prefers-reduced-motion: reduce)"),
      narrow = matchMedia("(max-width: 760px)");
    let visible = false;
    const update = () => {
      enable(visible && !document.hidden && !pref.matches);
      compact(narrow.matches);
    };
    const observer = new IntersectionObserver(([e]) => {
      visible = e.isIntersecting;
      update();
    });
    observer.observe(host.current!);
    pref.addEventListener("change", update);
    narrow.addEventListener("change", update);
    document.addEventListener("visibilitychange", update);
    return () => {
      observer.disconnect();
      pref.removeEventListener("change", update);
      narrow.removeEventListener("change", update);
      document.removeEventListener("visibilitychange", update);
    };
  }, []);
  return (
    <div className="art" ref={host}>
      <div className="art-scene" aria-hidden="true">
        {active && !paused && (
          <Fallback>
            <Vortex small={small} />
          </Fallback>
        )}
      </div>
      <div className="art-notes">
        <span>
          Counter-rotating vortices
          <br />
          Procedural illustration
        </span>
        {active && (
          <button
            onClick={() => pause(!paused)}
            aria-label={paused ? "Play illustration" : "Pause illustration"}
          >
            {paused ? "▷" : "Ⅱ"}
          </button>
        )}
      </div>
    </div>
  );
}
