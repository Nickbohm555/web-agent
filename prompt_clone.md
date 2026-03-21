You are running an iterative feature-harvesting loop.

You will be given a Company URL and a Feature log path at the end of this prompt.
Use those injected values.

Task:
1) Open the feature log (clone.md) and list features already captured. Avoid duplicates.
2) Using the Company URL, search the company's marketing pages, API docs, help center, blog/changelog, and reputable third-party coverage to find exactly ONE new feature not yet logged.
3) Append the new feature to clone.md with this exact structure:

feature N: <short feature name>
how it was likely done: <brief technical inference or confirmed implementation>

4) If you cannot find any new feature, create a file named .feature_scrape_done in the repo root and explain briefly why in your response.
5) Do NOT add multiple features in a single run.

Use web search as needed. Keep entries concise.
