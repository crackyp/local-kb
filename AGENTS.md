# Knowledge Base Schema

## What This Is
A personal knowledge base about [YOUR TOPIC].

## How It's Organized
- raw/ contains unprocessed source material. Never modify these files.
- wiki/ contains the organized wiki. AI maintains this entirely.
- outputs/ contains generated reports, answers, and analyses.

## Wiki Rules
- Merging safety: Only merge when the new raw document is highly relevant to the existing wiki page. If in doubt, create a new page instead of risking pollution.
- NEVER create a 1:1 wiki page for every raw file. 
- Synthesize: if multiple raw sources cover the same topic/concept, merge them into ONE cohesive wiki page.
- Only create a brand-new wiki page if the content introduces a genuinely new, distinct concept that does not meaningfully overlap with any existing page (checked via FAISS similarity).
- Prefer updating and expanding existing pages over creating duplicates.
- Every wiki file must start with a one-paragraph summary.
- Use [[topic-name]] style links liberally to connect related concepts.
- Maintain an INDEX.md that lists every topic.
- When new raw sources are added, first check for overlap with existing wiki pages before creating anything new.
- Always prefer merging over duplication.

## My Interests
[List 3-5 things you want this knowledge base to focus on]