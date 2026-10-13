// @vitest-environment jsdom
import { act } from 'react';
import { createRoot } from 'react-dom/client';
import { expect, it, vi } from 'vitest';
import { ReaderInstallGuide, READER_DOWNLOAD, READER_VERSION } from './ReaderInstallGuide';

it('shows shared versioned download and desktop installation without a collapsed panel', () => {
  vi.stubGlobal('IS_REACT_ACT_ENVIRONMENT', true);
  const host = document.createElement('div'); const root = createRoot(host);
  try {
    act(() => root.render(<ReaderInstallGuide />));
    expect(host.querySelector('a')?.getAttribute('href')).toBe(READER_DOWNLOAD);
    expect(host.textContent).toContain(READER_VERSION);
    for (const text of ['chrome://extensions', 'edge://extensions', 'manifest.json', '刷新', '旧版', '手机', 'degree-progress.json']) expect(host.textContent).toContain(text);
    expect(host.querySelectorAll('li')).toHaveLength(5);
    expect(host.querySelector('details')).toBeNull();
  } finally { act(() => root.unmount()); vi.unstubAllGlobals(); }
});
