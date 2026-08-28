import { useEffect, useState } from 'react';
import { getHealth, type Health } from './lib/http';

type State =
  | { kind: 'loading' }
  | { kind: 'error'; message: string }
  | { kind: 'ready'; health: Health };

export default function App() {
  const [state, setState] = useState<State>({ kind: 'loading' });

  useEffect(() => {
    let active = true;
    getHealth()
      .then((health) => {
        if (active) setState({ kind: 'ready', health });
      })
      .catch((err: unknown) => {
        if (active) {
          setState({
            kind: 'error',
            message: err instanceof Error ? err.message : 'Request failed',
          });
        }
      });
    return () => {
      active = false;
    };
  }, []);

  return (
    <main className="app">
      <h1>LoanFlow</h1>
      <p className="tagline">Maker–checker underwriting workbench</p>

      <section className="card">
        <h2>API status</h2>
        {state.kind === 'loading' && <p>Checking…</p>}
        {state.kind === 'error' && (
          <p className="err">Cannot reach the API: {state.message}</p>
        )}
        {state.kind === 'ready' && (
          <ul>
            <li>API: {state.health.status}</li>
            <li>Database: {state.health.db}</li>
          </ul>
        )}
      </section>

      <p className="hint">Phase P0 · see docs/ROADMAP.md</p>
    </main>
  );
}
