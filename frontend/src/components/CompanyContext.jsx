const publishedTime = value => new Intl.DateTimeFormat(undefined, {hour:'numeric', minute:'2-digit'}).format(new Date(value));

function Articles({items}) {
  return <div className="session-context-list">{items.map(item => <article key={item.id}>
    <p>{item.headline}</p>
    <div><span>{item.source_name} · {publishedTime(item.published_at)}</span>
      {item.source_url && <a href={item.source_url} target="_blank" rel="noreferrer">View source <span aria-hidden="true">↗</span></a>}
    </div>
  </article>)}</div>;
}

export default function CompanyContext({context, compact = false}) {
  const items = context?.company_developments || [];
  if (!items.length) return null;
  if (compact) return <details className="session-context compact">
    <summary>What was happening that day? <span>{items.length}</span></summary>
    <Articles items={items}/>
  </details>;
  return <section className="detail-panel session-context">
    <p className="eyebrow">RELEVANT CONTEXT</p>
    <h2>What was happening that day?</h2>
    <p className="context-note">Company developments published on the same trading date. This does not imply they caused the price movement.</p>
    <Articles items={items}/>
  </section>;
}
