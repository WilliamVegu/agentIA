// Load each application's existing Vite config, overriding only its listener/proxy.
import path from 'node:path';
import { createRequire } from 'node:module';
import { pathToFileURL } from 'node:url';

const [frontend, host, port, apiPort] = process.argv.slice(2);
const require = createRequire(path.join(frontend, 'package.json'));
const vitePackage = require.resolve('vite/package.json');
const { createServer } = await import(pathToFileURL(path.join(path.dirname(vitePackage), 'dist/node/index.js')));
const server = await createServer({
  root: frontend,
  server: {
    host,
    port: Number(port),
    strictPort: true,
    open: false,
    proxy: Object.fromEntries(['/api', '/healthz'].map(prefix => [prefix, {
      target: `http://127.0.0.1:${apiPort}`,
      changeOrigin: true,
    }])),
  },
});
await server.listen();
server.printUrls();
const stop = async () => { await server.close(); process.exit(0); };
process.on('SIGINT', stop);
process.on('SIGTERM', stop);
