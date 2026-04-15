const MAX_SCORES = {
  bullet_strength: 30,
  skill_coverage: 25,
  project_impact: 25,
  education: 10,
  completeness: 10,
}

function getClass(score) {
  if (score >= 71) return 'green'
  if (score >= 41) return 'yellow'
  return 'red'
}

export default function ScorePanel({ evaluation }) {
  const { score, section_scores, reasoning } = evaluation
  const cls = getClass(score)

  return (
    <div className="retro-card">
      <div className="retro-card-header">📊 RESUME SCORE ANALYSIS</div>
      <div className="retro-card-body">

        <div style={{ textAlign: 'center', marginBottom: '16px' }}>
          <div className={`score-number ${cls}`}>{score}<span style={{ fontSize: '24px' }}>/100</span></div>
          <div className="score-meter">
            <div className={`score-fill ${cls}`} style={{ width: `${score}%` }} />
          </div>
          <div style={{ fontFamily: '"VT323", monospace', fontSize: '20px', color: '#aaaaaa', marginTop: '4px', letterSpacing: '2px' }}>
            {cls === 'green' ? '★ STRONG CANDIDATE' : cls === 'yellow' ? '◆ NEEDS IMPROVEMENT' : '▼ MAJOR REVISION NEEDED'}
          </div>
        </div>

        <hr className="retro-divider" />

        <div style={{ marginBottom: '14px' }}>
          <div className="retro-label" style={{ marginBottom: '8px' }}>⊞ SECTION BREAKDOWN</div>
          <table className="section-scores">
            <tbody>
              {Object.entries(section_scores).map(([key, val]) => (
                <tr key={key}>
                  <td className="score-label">{key.replace(/_/g, ' ')}</td>
                  <td className="score-bar-td">
                    <div className="mini-meter">
                      <div className="mini-fill" style={{ width: `${(val / MAX_SCORES[key]) * 100}%` }} />
                    </div>
                  </td>
                  <td className="score-val">{val}/{MAX_SCORES[key]}</td>
                </tr>
              ))}
            </tbody>
          </table>
        </div>

        <hr className="retro-divider" />

        <div className="retro-label" style={{ marginBottom: '8px' }}>💬 AI REASONING</div>
        <ul className="reasoning-list">
          {reasoning.map((r, i) => <li key={i}>{r}</li>)}
        </ul>
      </div>
    </div>
  )
}
