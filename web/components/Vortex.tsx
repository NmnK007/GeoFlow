"use client";
import { Canvas, useFrame } from "@react-three/fiber";
import { useMemo, useRef } from "react";
import { AdditiveBlending, ShaderMaterial, Group } from "three";

const vertex = `
uniform float clockTime;
attribute float glow;
varying float light;
varying float side;
void main(){
 float r=position.x, t=position.y, s=position.z;
 float a=t+s*(2.15*r+clockTime*(0.13+0.2/(0.55+r)));
 float k=1.0+.15*sin(3.*a+2.*r)+.1*cos(2.*a-r);
 vec3 p=vec3(s*1.02+1.12*r*k*cos(a),.58*r*k*sin(a)+s*.23,.34*sin(a+s*.5)*r+.72*exp(-r*r*2.5));
 p.x+=.26*sin(p.y*2.4); p.y+=.16*p.x+.10*sin(p.x*2.4);
 vec4 mv=modelViewMatrix*vec4(p,1.);
 gl_Position=projectionMatrix*mv;
 gl_PointSize=clamp((1.+1.2*glow)*4.7/-mv.z,1.,3.);
 light=glow*(.56+.44*cos(a-.65)); side=s;
}`;
const fragment = `
varying float light;
varying float side;
void main(){float d=length(gl_PointCoord-.5)*2.;if(d>1.)discard;
 vec3 c=mix(vec3(.21,.66,.40),vec3(.80,1.,.62),light);
 if(side<0.)c=mix(c,vec3(.45,.79,.69),.37);
 gl_FragColor=vec4(c,(1.-d*d)*(.24+.73*light));}
`;
function Points({ small }: { small: boolean }) {
  const material = useRef<ShaderMaterial>(null),
    group = useRef<Group>(null);
  const uniforms = useMemo(() => ({ clockTime: { value: 0 } }), []);
  const [positions, glows] = useMemo(() => {
    const rings = small ? 64 : 116,
      samples = small ? 65 : 120,
      count = rings * samples * 2,
      p = new Float32Array(count * 3),
      g = new Float32Array(count);
    let index = 0;
    for (const s of [-1, 1])
      for (let j = 0; j < rings; j++)
        for (let k = 0; k < samples; k++) {
          const seed = Math.sin((j * 547 + k * 41 + s) * 12.98) * 43758.54,
            noise = seed - Math.floor(seed);
          p[index * 3] = 0.08 + (1.55 * (j + 0.25 * noise)) / rings;
          p[index * 3 + 1] =
            (Math.PI * 2 * (k + 0.24 * noise)) / samples +
            0.21 * Math.sin(j * 0.25);
          p[index * 3 + 2] = s;
          g[index++] = 0.15 + 0.83 * noise;
        }
    return [p, g];
  }, [small]);
  useFrame((state, dt) => {
    if (!material.current || !group.current) return;
    material.current.uniforms.clockTime.value += Math.min(dt, 0.075);
    const a = 1 - Math.exp(-dt * 2.4);
    group.current.rotation.y +=
      (state.pointer.x * 0.1 - group.current.rotation.y) * a;
    group.current.rotation.x +=
      (-0.16 +
        state.pointer.y * 0.06 -
        Math.min(window.scrollY / 1000, 0.6) * 0.12 -
        group.current.rotation.x) *
      a;
  });
  return (
    <group ref={group}>
      <points frustumCulled={false}>
        <bufferGeometry>
          <bufferAttribute attach="attributes-position" args={[positions, 3]} />
          <bufferAttribute attach="attributes-glow" args={[glows, 1]} />
        </bufferGeometry>
        <shaderMaterial
          ref={material}
          uniforms={uniforms}
          vertexShader={vertex}
          fragmentShader={fragment}
          blending={AdditiveBlending}
          transparent
          depthWrite={false}
        />
      </points>
    </group>
  );
}
export default function Vortex({ small }: { small: boolean }) {
  return (
    <Canvas
      aria-hidden
      camera={{ position: [0, 0, 5.3], fov: 34 }}
      dpr={small ? 1 : [1, 1.35]}
      gl={{ alpha: true, antialias: false, powerPreference: "low-power" }}
    >
      <Points small={small} />
    </Canvas>
  );
}
