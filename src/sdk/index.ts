export interface SearchOptions {}

export interface SearchResult {
  readonly query: string;
  readonly results: readonly unknown[];
}

export interface FetchOptions {}

export interface FetchResult {
  readonly url: string;
  readonly content: string;
}

export async function search(
  query: string,
  _options: SearchOptions = {},
): Promise<SearchResult> {
  return {
    query,
    results: [],
  };
}

export async function fetch(
  url: string,
  _options: FetchOptions = {},
): Promise<FetchResult> {
  return {
    url,
    content: "",
  };
}
