import express, {
  type Application,
  Router,
  type RequestHandler,
} from "express";
import path from "node:path";
import { fileURLToPath } from "node:url";

const DEFAULT_PORT = 3000;
const JSON_LIMIT = "100kb";
const __dirname = path.dirname(fileURLToPath(import.meta.url));
const projectRoot = path.resolve(__dirname, "../..");
const publicDir = path.join(projectRoot, "public");
const publicIndexPath = path.join(publicDir, "index.html");

function createPendingRoute(operation: "search" | "fetch"): RequestHandler {
  return (_req, res) => {
    res.status(501).json({
      ok: false,
      operation,
      error: {
        code: "NOT_IMPLEMENTED",
        message: `${operation} API route is scaffolded but not implemented yet.`,
      },
    });
  };
}

function createApiRouter(): Router {
  const router = Router();

  router.use("/search", createPendingRoute("search"));
  router.use("/fetch", createPendingRoute("fetch"));

  return router;
}

export function createFrontendServerApp(): Application {
  const app = express();

  app.disable("x-powered-by");
  app.use(express.json({ limit: JSON_LIMIT }));
  app.use("/api", createApiRouter());
  app.use(express.static(publicDir));

  app.get(/^(?!\/api(?:\/|$)).*/, (_req, res, next) => {
    res.sendFile(publicIndexPath, (error) => {
      if (error) {
        next();
      }
    });
  });

  return app;
}

export async function startFrontendServer(port = DEFAULT_PORT) {
  const app = createFrontendServerApp();

  return await new Promise<{
    app: Application;
    port: number;
    close: () => Promise<void>;
  }>((resolve, reject) => {
    const server = app.listen(port, () => {
      resolve({
        app,
        port,
        close: async () =>
          await new Promise<void>((closeResolve, closeReject) => {
            server.close((error) => {
              if (error) {
                closeReject(error);
                return;
              }

              closeResolve();
            });
          }),
      });
    });

    server.on("error", reject);
  });
}

if (import.meta.url === `file://${process.argv[1]}`) {
  const portValue = Number.parseInt(process.env.PORT ?? `${DEFAULT_PORT}`, 10);
  const port = Number.isNaN(portValue) ? DEFAULT_PORT : portValue;

  startFrontendServer(port)
    .then(({ port: boundPort }) => {
      process.stdout.write(
        `Frontend server listening on http://127.0.0.1:${boundPort}\n`,
      );
    })
    .catch((error: unknown) => {
      process.stderr.write(
        `Failed to start frontend server: ${
          error instanceof Error ? error.message : String(error)
        }\n`,
      );
      process.exitCode = 1;
    });
}
