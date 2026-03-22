import express, {
  type Application,
  Router,
} from "express";
import { access, readFile } from "node:fs/promises";
import { constants as fsConstants } from "node:fs";
import path from "node:path";
import { fileURLToPath } from "node:url";
import ts from "typescript";
import { withRunContext } from "../core/telemetry/run-context.js";
import { createFetchRouter } from "./routes/fetch.js";
import { createRunHistoryRouter } from "./routes/run-history.js";
import {
  createHttpAgentRunExecutor,
  createRunsRouter,
} from "./routes/runs.js";
import { createSearchRouter } from "./routes/search.js";
import { createRunHistoryStore } from "./run-history/store.js";

const DEFAULT_PORT = 3000;
const JSON_LIMIT = "100kb";
const __dirname = path.dirname(fileURLToPath(import.meta.url));
const projectRoot = path.resolve(__dirname, "../..");
const publicDir = path.join(projectRoot, "public");
const publicIndexPath = path.join(publicDir, "index.html");
const srcDir = path.join(projectRoot, "src");
const frontendSourceDir = path.join(srcDir, "frontend");

function createApiRouter(): Router {
  const router = Router();

  router.use("/search", createSearchRouter());
  router.use("/fetch", createFetchRouter());
  router.use("/runs", createRunHistoryRouter());
  router.use("/runs", createRunsRouter());

  return router;
}

export function createFrontendServerApp(): Application {
  const app = express();
  const apiRouter = createApiRouter();
  const backendAgentOrigin = process.env.AGENT_BACKEND_ORIGIN?.trim();

  app.locals.runHistoryStore = createRunHistoryStore();
  if (backendAgentOrigin) {
    app.locals.runExecutor = createHttpAgentRunExecutor(backendAgentOrigin);
  }

  app.disable("x-powered-by");
  app.use(express.json({ limit: JSON_LIMIT }));
  app.use("/api", (req, res, next) => {
    const headerRunId = req.header("x-run-id");
    const options =
      typeof headerRunId === "string" ? { runId: headerRunId } : undefined;

    withRunContext(
      () => {
        apiRouter(req, res, next);
      },
      options,
    );
  });
  app.get(/^\/(?<modulePath>.+)\.js$/, async (req, res, next) => {
    const sourcePath = await resolveBrowserModuleSourcePath(req.path);
    if (sourcePath === null) {
      next();
      return;
    }

    try {
      const source = await readFile(sourcePath, "utf8");
      const output = ts.transpileModule(source, {
        compilerOptions: {
          module: ts.ModuleKind.ESNext,
          target: ts.ScriptTarget.ES2022,
        },
        fileName: sourcePath,
      });

      res.type("application/javascript").send(output.outputText);
    } catch (error: unknown) {
      next(error);
    }
  });
  app.get("/healthz", (_req, res) => {
    res.status(200).json({ status: "ok" });
  });
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

async function resolveBrowserModuleSourcePath(requestPath: string): Promise<string | null> {
  const match = /^\/(?<modulePath>.+)\.js$/.exec(requestPath);
  const modulePath = match?.groups?.modulePath;
  if (modulePath === undefined) {
    return null;
  }

  const normalizedModulePath = path.posix.normalize(modulePath);
  if (
    normalizedModulePath.length === 0 ||
    normalizedModulePath.startsWith("../") ||
    normalizedModulePath.includes("/../")
  ) {
    return null;
  }

  const candidateRelativePath = normalizedModulePath.replace(/^\/+/, "") + ".ts";
  const candidateRoots = [frontendSourceDir, srcDir];

  for (const root of candidateRoots) {
    const candidatePath = path.resolve(root, candidateRelativePath);
    if (!candidatePath.startsWith(root + path.sep)) {
      continue;
    }

    try {
      await access(candidatePath, fsConstants.R_OK);
      return candidatePath;
    } catch {
      continue;
    }
  }

  return null;
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
