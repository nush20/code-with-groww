export default function BrandMark({className = ''}) {
  return <svg className={className} viewBox="0 0 40 40" role="img" aria-label="MarketMemo logo">
    <rect x="1" y="1" width="38" height="38" rx="11" fill="currentColor" />
    <path d="M12.5 11.5h10.8l4.2 4.2v12.8h-15z" fill="none" stroke="white" strokeWidth="2" strokeLinejoin="round" />
    <path d="M23.3 11.5v4.3h4.2" fill="none" stroke="white" strokeWidth="2" strokeLinejoin="round" />
    <path d="m15.8 24.2 3.2-3.4 2.7 2.2 3.5-4.2" fill="none" stroke="white" strokeWidth="2.2" strokeLinecap="round" strokeLinejoin="round" />
  </svg>;
}
