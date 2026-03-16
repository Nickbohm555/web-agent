import { Readability } from "@mozilla/readability";
import { load } from "cheerio";
import TurndownService from "turndown";

export type ExtractionState =
  | "OK"
  | "LOW_CONTENT_QUALITY"
  | "UNSUPPORTED_CONTENT_TYPE";

export interface ExtractContentOptions {
  minTextLength?: number;
}

export interface ExtractContentSuccessResult {
  state: "OK";
  text: string;
  markdown: string;
  title: string | null;
}

export interface ExtractContentLowQualityResult {
  state: "LOW_CONTENT_QUALITY";
  text: string;
  markdown: string;
  title: string | null;
}

export interface ExtractContentUnsupportedResult {
  state: "UNSUPPORTED_CONTENT_TYPE";
  text: "";
  markdown: "";
  title: null;
}

export type ExtractContentResult =
  | ExtractContentSuccessResult
  | ExtractContentLowQualityResult
  | ExtractContentUnsupportedResult;

const DEFAULT_MIN_TEXT_LENGTH = 120;
const turndownService = new TurndownService({
  headingStyle: "atx",
  codeBlockStyle: "fenced",
});

export function extractContent(
  html: string,
  contentType: string | null,
  options: ExtractContentOptions = {},
): ExtractContentResult {
  if (!isSupportedContentType(contentType)) {
    return {
      state: "UNSUPPORTED_CONTENT_TYPE",
      text: "",
      markdown: "",
      title: null,
    };
  }

  const $ = load(html);
  $("script, style, noscript, iframe, svg").remove();

  const title = readTitle($("title").first().text());
  const preferredRoot = $("main").first().html()
    ?? $("article").first().html()
    ?? $("body").first().html()
    ?? $.root().html()
    ?? "";

  const readabilityCandidate = parseWithReadability(html);
  const candidateHtml = readabilityCandidate?.content?.trim() || preferredRoot;
  const textSource = readabilityCandidate?.textContent?.trim() || $(preferredRoot).text();
  const text = normalizeWhitespace(textSource);
  const markdown = normalizeWhitespace(
    candidateHtml ? turndownService.turndown(candidateHtml) : "",
  );

  if (text.length < (options.minTextLength ?? DEFAULT_MIN_TEXT_LENGTH)) {
    return {
      state: "LOW_CONTENT_QUALITY",
      text,
      markdown,
      title,
    };
  }

  return {
    state: "OK",
    text,
    markdown,
    title,
  };
}

function isSupportedContentType(contentType: string | null): boolean {
  if (contentType === null) {
    return true;
  }

  return /text\/html|application\/xhtml\+xml/i.test(contentType);
}

function normalizeWhitespace(input: string): string {
  return input.replace(/\s+/g, " ").trim();
}

function readTitle(input: string): string | null {
  const title = normalizeWhitespace(input);
  return title.length > 0 ? title : null;
}

function parseWithReadability(html: string): {
  content: string | null;
  textContent: string | null;
} | null {
  const domParser = (globalThis as {
    DOMParser?: {
      new (): {
        parseFromString: (input: string, mimeType: string) => unknown;
      };
    };
  }).DOMParser as
    | {
        new (): {
          parseFromString: (input: string, mimeType: string) => unknown;
        };
      }
    | undefined;

  if (typeof domParser !== "function") {
    return null;
  }

  try {
    const document = new domParser().parseFromString(html, "text/html");
    const article = new Readability(document).parse();

    return article
      ? {
          content: article.content ?? null,
          textContent: article.textContent ?? null,
        }
      : null;
  } catch {
    return null;
  }
}
