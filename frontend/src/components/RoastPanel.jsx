export default function RoastPanel({ roast }) {
  const { roast: roastItems, verdict, one_liner } = roast

  return (
    <div className="retro-card">
      <div className="retro-card-header">🔥 RESUME ROAST — BRUTALLY HONEST EDITION</div>
      <div className="retro-card-body">

        <div className="roast-one-liner">
          &ldquo;{one_liner}&rdquo;
        </div>

        {roastItems.map((item, i) => (
          <div key={i} className="roast-item">
            <div className="roast-target">▶ {item.target}</div>
            <div className="roast-hot-take">{item.hot_take}</div>
          </div>
        ))}

        <div className="roast-verdict">
          <span style={{
            color: '#FFD700',
            textTransform: 'uppercase', fontSize: '18px',
            fontFamily: '"VT323", monospace',
            letterSpacing: '2px',
          }}>
            FINAL VERDICT:&nbsp;
          </span>
          {verdict}
        </div>
      </div>
    </div>
  )
}
