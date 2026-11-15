# Transcript fixtures

`weeknight_curry_panel.txt` is a made-up cooking video transcript, written for
these tests. It is not copied from any real video. It is laid out the way
YouTube's "Show transcript" panel copies to the clipboard: a timestamp on one
line, the caption text on the next, lowercase with no punctuation, the way
auto-captions come.

230 lines: 115 timestamps, 113 caption segments and two `[Music]` sound tags.
4,059 characters of caption text.

| From | What |
|---|---|
| 0:00 | `[Music]`, then greeting chatter with nothing about cooking |
| 0:33 | the dish is named: "easy weeknight chicken curry with coconut milk and spinach" |
| 0:45 | sponsor read for a made-up meal kit ("larder box"). Sponsor phrases at 0:48 ("sponsor of") and 1:27 to 1:30 ("use code", "percent off"). Food words in between ("lemon chicken pasta", "beef tacos") with no sponsor phrase near them |
| 1:30 | tail of the read ("that is larder box dot com the link is down below"), then thanks and chatter with nothing about cooking |
| 2:23 | cooking, part 1: oil, onion, garlic, ginger, curry powder, tomato paste, chicken thighs, salt, with spoken amounts |
| 3:32 | a personal story with nothing about cooking; "denver" at 4:02 sits in the middle of it |
| 4:57 | `[Music]`, then cooking, part 2: coconut milk, chicken stock, spinach, lime, rice, cilantro; "dinner for four people" |
| 5:43 | sign-off with nothing about cooking; "subscribe" at 6:20 |

The stretches with nothing about cooking are each longer than one passage
(320 characters), so a filter that works on passages can drop them whole
whatever its exact boundaries are.
