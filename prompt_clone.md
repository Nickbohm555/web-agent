You are running an iterative feature-harvesting loop.

You will be given a Company URL and a Feature log path at the end of this prompt.
Use those injected values.

Task:
1) Open the feature log (clone.md) and list features already captured. Avoid duplicates.
2) Check existing entries in clone.md. If any existing feature entry is missing a short description, update exactly one incomplete existing entry first by adding the missing description before adding any new feature.
3) Using the Company URL, search the company's marketing pages, API docs, help center, blog/changelog, and reputable third-party coverage to find exactly ONE new feature not yet logged, but only if no existing entry needs its missing description filled in.
4) Append the new feature to clone.md with this exact structure:

feature N: <short feature name>
what it does: <short description of the feature in 1-2 sentences>
how it was likely done: <brief technical inference or confirmed implementation>

5) When updating an older incomplete entry, preserve its numbering and title and add:

what it does: <short description of the feature in 1-2 sentences>

before touching any new feature entry.
6) If you cannot find any new feature, create a file named .feature_scrape_done in the repo root and explain briefly why in your response.
7) Do NOT add multiple features in a single run.

Use web search as needed. Keep entries concise.
