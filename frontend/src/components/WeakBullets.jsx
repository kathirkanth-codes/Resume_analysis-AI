export default function WeakBullets({ weakPoints }) {
  return (
    <div className="retro-card">
      <div className="retro-card-header">⚠ WEAK BULLET POINTS DETECTED</div>
      <div className="retro-card-body">
        {weakPoints.length === 0 ? (
          <div style={{ color: '#00FF00', fontFamily: '"VT323", monospace', fontSize: '20px', letterSpacing: '1px' }}>
            ✔ No weak bullets found — nice work!
          </div>
        ) : (
          weakPoints.map((item, i) => (
            <div key={i} style={{ marginBottom: '18px' }}>
              <div style={{
                fontFamily: '"VT323", monospace',
                fontSize: '18px', color: '#FF4444', marginBottom: '4px', textTransform: 'uppercase', letterSpacing: '1px'
              }}>
                ✗ ORIGINAL:
              </div>
              <div className="bullet-original">{item.original}</div>

              <div style={{
                fontFamily: '"VT323", monospace',
                fontSize: '18px', color: '#00FF00', margin: '6px 0 4px', textTransform: 'uppercase', letterSpacing: '1px'
              }}>
                ✔ IMPROVED:
              </div>
              <div className="bullet-improved">{item.improved}</div>
            </div>
          ))
        )}
      </div>
    </div>
  )
}
