"use client";
import Link from "next/link";
import { Notice, api, useData } from "../../components/shared";

type Table = {title: string; method: string; columns: string[]; source: string;
  rows: (number | string | null)[][]};

export default function Research() {
  const report = useData<Table[]>("/research");
  return <article className="lab stack evidence">
    <h1>Research &amp; verification</h1>
    <p className="intro">How accurately do the equations reproduce a known wave, an observed drift, or a numerical reference? Each table gives the experiment, units and comparison behind its result.</p>
    <p>Explore the archived <Link href="/simulation">fluid simulations</Link>, <Link href="/earth">Arabian Sea tracks</Link>, <Link href="/neural">surrogate fields</Link> and <Link href="/hpc">hardware measurements</Link>.</p>
    {!report && <p role="status">Loading verification records…</p>}
    <Notice error={report?.error}/>
    {report?.data?.map(t => <section key={t.title} className="panel stack">
      <h2>{t.title}</h2><p>{t.method}</p>
      <div className="evidence-scroll" role="region" aria-label={t.title} tabIndex={0}>
        <table><caption>Archive · {t.source}</caption>
          <thead><tr>{t.columns.map(c => <th scope="col" key={c}>{c}</th>)}</tr></thead>
          <tbody>{t.rows.map((row,i) => <tr key={i}>{row.map((v,j) =>
            j === 0 ? <th scope="row" key={j}>{v}</th> : <td key={j}>{v === null ? "—" : String(v)}</td>)}</tr>)}</tbody>
        </table>
      </div>
    </section>)}
    <a href={api + "/research"} download="geoflow-evidence.json">Download displayed records (JSON)</a>
  </article>;
}
