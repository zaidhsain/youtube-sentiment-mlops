"""Page de test qui reproduit la structure DOM des commentaires YouTube.

Servie à l'URL https://www.youtube.com/watch?v=demo par interception Playwright
(aucune requête n'atteint YouTube). Simule le chargement progressif au défilement :
20 fils de commentaires au départ, +20 à chaque arrivée en bas de page.
Les commentaires et pseudos sont fictifs.
"""
import html
import json

TITLE = "Docker in 10 Minutes — Containers Explained for Beginners"

COMMENTS = [
    ("@devmaria", "This is the best Docker tutorial I have ever watched, thank you so much!"),
    ("@kevin_codes", "Great explanation, finally understood the difference between images and containers"),
    ("@sara.lee", "The audio is terrible, I could barely hear anything"),
    ("@techguy42", "Watched on March 3rd"),
    ("@anon_user", "Honestly this was boring and way too slow"),
    ("@pythonista", "Amazing work, very clear and helpful 😍"),
    ("@lina_dev", "What version of Docker are you using in the video?"),
    ("@marc", "Worst explanation of volumes ever, totally wrong"),
    ("@yousra.b", "Thanks a lot, this helped me pass my cloud exam!"),
    ("@hamza_ml", "Can you make a video about Kubernetes next"),
    ("@coder_x", "I love how simple you made it, perfect for beginners"),
    ("@jane", "The background music is so annoying, I stopped watching"),
    ("@omar", "Timestamp 4:20 for the Dockerfile part"),
    ("@zoe", "Really good content, subscribed"),
    ("@ali_k", "This tutorial is outdated and useless now"),
    ("@nina", "Docker compose explained at the end"),
    ("@sam_ops", "Excellent video, clean and well structured"),
    ("@frank", "Stupid clickbait title, nothing new here"),
    ("@leo", "Recorded in 4K?"),
    ("@meryem", "Very nice, the best channel for devops"),
    ("@ibrahim", "I hate when people skip the networking part"),
    ("@claire", "Perfect pace, great examples, thank you"),
    ("@tom", "Linux or Windows for this?"),
    ("@aya", "This saved my project, you are awesome"),
    ("@victor", "Bad quality and confusing slides"),
    ("@sofia", "Watching from Rabat"),
    ("@mehdi", "Super clear, best tutorial on youtube"),
    ("@paul", "Pretty pathetic attempt at explaining layers"),
    ("@ines", "Part 2 when?"),
    ("@reda", "Wonderful explanation, everything makes sense now"),
    ("@emma", "Too much talking and the code is wrong at 6:10"),
    ("@yassine", "Good job, keep it up"),
    ("@lucas", "Uploaded the same day as the release"),
    ("@salma", "Brilliant, I finally get what a container is"),
    ("@noah", "Disappointing, expected much more depth"),
    ("@hind", "Thank you, very useful for my internship"),
    ("@adam", "Dark mode editor theme name?"),
    ("@karim", "Awful microphone, painful to listen"),
    ("@julia", "Great video and great energy"),
    ("@walid", "Mac M1 here"),
    ("@laila", "The best teacher, so happy I found this channel"),
    ("@ben", "Wrong information about port mapping, be careful"),
    ("@chaima", "Nice and short, exactly what I needed"),
    ("@nabil", "Day 3 of learning devops"),
    ("@ruth", "Horrible editing, too many cuts"),
    ("@anas", "Incredible quality for a free course, thank you"),
    ("@eva", "Second time watching"),
    ("@driss", "I love this, more videos like this please"),
    ("@max", "Boring, I fell asleep"),
    ("@imane", "Very helpful and well explained"),
    ("@ilyas", "Which IDE is that?"),
    ("@sophie", "Great, great, great! Best explanation"),
    ("@oussama", "Sad that the repo link is broken"),
    ("@nora", "Clear, concise and fun to watch"),
    ("@henri", "Posted from my phone"),
    ("@kenza", "This is gold, thank you so much"),
    ("@igor", "Bad advice about running as root"),
    ("@rania", "Thanks, helped a lot with my TP cloud"),
    ("@will", "English subtitles please"),
    ("@hajar", "Excellent, very good examples"),
]
REPLIES = {
    0: [("@kevin_codes", "Agreed, really great work")],
    2: [("@channel", "Sorry about that, fixed in the next video")],
    7: [("@devmaria", "I think it was fine actually, good enough for beginners")],
}

PAGE = """<!doctype html><html><head><meta charset="utf-8"><title>{title} - YouTube</title>
<style>
 body{{font-family:Roboto,Arial,sans-serif;margin:0;background:#fff;color:#0f0f0f}}
 .top{{height:56px;display:flex;align-items:center;padding:0 16px;border-bottom:1px solid #eee;font-weight:700}}
 .top b{{background:#f00;color:#fff;border-radius:6px;padding:2px 6px;margin-right:6px}}
 .wrap{{max-width:900px;margin:16px 24px}}
 .player{{aspect-ratio:16/9;background:#111;border-radius:12px;display:grid;place-items:center;color:#aaa}}
 h1{{font-size:20px}} ytd-comment-thread-renderer{{display:block;margin:16px 0}}
 #author-text{{font-weight:600;font-size:13px}} #content-text{{display:block;font-size:14px;margin-top:2px}}
 ytd-comment-replies-renderer{{display:block;margin-left:48px}}
 .fixture{{background:#fff4ce;padding:6px 10px;border-radius:8px;font-size:12px}}
</style></head><body>
<div class="top"><b>▶</b>YouTube <span style="margin-left:12px;font-weight:400;font-size:12px">(page de test — structure DOM reproduite)</span></div>
<div class="wrap">
 <div class="player">▶ vidéo</div>
 <h1 class="ytd-watch-metadata">{title}</h1>
 <p class="fixture">Fixture de test E2E : commentaires fictifs, chargés progressivement au défilement comme sur YouTube.</p>
 <ytd-comments id="comments"><h2>{n} Comments</h2><div id="contents"></div></ytd-comments>
</div>
<script>
const DATA = {data};
const REPLIES = {replies};
let shown = 0;
function esc(s){{const d=document.createElement('div');d.textContent=s;return d.innerHTML}}
function addBatch(){{
  const box = document.getElementById('contents');
  const end = Math.min(shown + 20, DATA.length);
  for (; shown < end; shown++) {{
    const [a, t] = DATA[shown];
    const th = document.createElement('ytd-comment-thread-renderer');
    let rep = '';
    if (REPLIES[shown]) rep = '<ytd-comment-replies-renderer>' + REPLIES[shown].map(([ra, rt]) =>
      `<ytd-comment-view-model><a id="author-text">${{esc(ra)}}</a><span id="content-text">${{esc(rt)}}</span></ytd-comment-view-model>`).join('') + '</ytd-comment-replies-renderer>';
    th.innerHTML = `<ytd-comment-view-model><a id="author-text">${{esc(a)}}</a><span id="content-text">${{esc(t)}}</span></ytd-comment-view-model>${{rep}}`;
    box.appendChild(th);
  }}
}}
addBatch();
addEventListener('scroll', () => {{
  if (innerHeight + scrollY >= document.documentElement.scrollHeight - 50 && shown < DATA.length)
    setTimeout(addBatch, 400);   // latence réseau simulée
}});
</script></body></html>"""


def render() -> str:
    return PAGE.format(
        title=html.escape(TITLE), n=len(COMMENTS),
        data=json.dumps(COMMENTS), replies=json.dumps({str(k): v for k, v in REPLIES.items()}),
    )
