# Link check — 2026-09-28

Method: `curl -sI` for every `https://` URL in `README.md`
(resources/ files link to the same URL set). All URLs were opened this run.

```
200 https://creativecommons.org/licenses/by/4.0/
200 https://gate2025.iitr.ac.in
200 https://gate2026.iitg.ac.in
200 https://gate2027.iitm.ac.in
200 https://github.com/lakhidas168-ship-it/awesome-indian-exams
200 https://github.com/lakhidas168-ship-it/awesome-indian-exams/blob/main/awesome-indian-exams/exams/engineering/gate-ee.md
200 https://github.com/lakhidas168-ship-it/awesome-indian-exams/blob/main/awesome-indian-exams/exams/engineering/psu-ee.md
200 https://github.com/lakhidas168-ship-it/awesome-indian-exams/blob/main/awesome-indian-exams/exams/engineering/rrb-je-ee.md
200 https://github.com/lakhidas168-ship-it/awesome-indian-exams/blob/main/awesome-indian-exams/exams/engineering/ssc-je-ee.md
200 https://github.com/lakhidas168-ship-it/awesome-indian-exams/blob/main/awesome-indian-exams/exams/engineering/state-ae-je.md
200 https://github.com/lakhidas168-ship-it/awesome-indian-exams/blob/main/awesome-indian-exams/exams/engineering/upsc-ese-ee.md
200 https://indianrailways.gov.in
200 https://nptel.ac.in
200 https://nptel.ac.in/courses/108102096
200 https://nptel.ac.in/courses/108102146
200 https://nptel.ac.in/courses/108104087
200 https://nptel.ac.in/courses/108104100
200 https://nptel.ac.in/courses/108105017
200 https://nptel.ac.in/courses/108105064
200 https://nptel.ac.in/courses/108105067
200 https://nptel.ac.in/courses/108105132
200 https://nptel.ac.in/courses/108105159
200 https://nptel.ac.in/courses/108106098
200 https://ssc.gov.in
307 https://upsc.gov.in
200 https://www.rrbapply.gov.in/
```

Result: 26/26 return 2xx/3xx.

Notes:
- `upsc.gov.in` answers 307 to HEAD (redirect to `www.upsc.gov.in`, which is 200) — counts as 3xx pass.
- `rrbapply.gov.in` (apex) does not answer from here; the `www` host (verified 200 above) is what the README links.
- The hub example path `exams/engineering/gate-ee.md` (repo-root relative) 404s; the real
  hub path is `awesome-indian-exams/exams/engineering/gate-ee.md` (verified 200) and that is what is linked.
- The repo's own future clone URL (`.../awesome-electrical-exams`) 404s because this repo
  is local-only (not pushed); it is deliberately not linked from the README.
