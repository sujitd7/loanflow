import { render, screen, waitFor } from '@testing-library/react';
import { afterEach, beforeEach, expect, test, vi } from 'vitest';
import App from './App';

beforeEach(() => {
  vi.stubGlobal(
    'fetch',
    vi.fn(
      async () =>
        new Response(JSON.stringify({ status: 'ok', db: 'ok' }), {
          status: 200,
          headers: { 'Content-Type': 'application/json' },
        }),
    ),
  );
});

afterEach(() => {
  vi.unstubAllGlobals();
});

test('renders the API status once the health check resolves', async () => {
  render(<App />);

  expect(screen.getByText('Checking…')).toBeInTheDocument();

  await waitFor(() => {
    expect(screen.getByText('Database: ok')).toBeInTheDocument();
  });
});
