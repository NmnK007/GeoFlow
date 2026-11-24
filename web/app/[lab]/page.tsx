import { notFound } from "next/navigation";
import Simulation from "../../components/Simulation";
import Earth from "../../components/Earth";
import Neural from "../../components/Neural";
import HPC from "../../components/HPC";
const modules = {
  simulation: Simulation,
  earth: Earth,
  neural: Neural,
  hpc: HPC,
};
export function generateStaticParams() {
  return Object.keys(modules).map((lab) => ({ lab }));
}
export default async function Page({
  params,
}: {
  params: Promise<{ lab: string }>;
}) {
  const { lab } = await params;
  if (!Object.hasOwn(modules, lab)) notFound();
  const Lab = modules[lab as keyof typeof modules];
  return (
    <article className="lab">
      <Lab />
    </article>
  );
}
