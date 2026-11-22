# Space browser suite

End-to-end checks for the Hugging Face Space
([re-cep/vitiligo-curative-discovery](https://huggingface.co/spaces/re-cep/vitiligo-curative-discovery)),
driven through headless Chrome by a dependency-free DevTools driver (`cdp.mjs`, Node 22
or later). Expected values are computed from the Space's JSON files, independently of
`app.js`, so a check fails when the page shows something its data does not say.

CI does not run it (it needs Chrome). Run it before every deploy, against the folder,
and after, against the live Space.

```sh
python -m http.server 8765 --directory exports/hf_space    # in one shell
node tests/space/test_space.mjs http://127.0.0.1:8765 exports/hf_space /tmp/space-downloads
TRACE=1 node tests/space/test_space.mjs ...                 # print every passing check
node tests/space/test_space.mjs https://re-cep-vitiligo-curative-discovery.static.hf.space \
  exports/hf_space /tmp/space-downloads                     # the live Space
```

Chrome is taken from `/Applications/Google Chrome.app`; set `CHROME_PATH` elsewhere.
Every DevTools call times out after 60 s. The live run takes ten minutes or more, and
right after a deploy the host's cache is cold: the first uncompressed (fallback) load of
the trials view took 51.6 s, later ones 4-8 s, so those checks allow a minute.

| File | What it does |
|---|---|
| `test_space.mjs` | Close to 300 checks: every view's figures, tables, filters, dialogs and CSV downloads against the JSON; gzip fallbacks; a run with the paper results blocked; phone widths; console errors |
| `shoot.mjs` | Screenshots (desktop light and dark, phone) of the routes given: `node tests/space/shoot.mjs <base url> <out dir> [route ...]` |
| `widths.mjs` | No sideways page scroll at in-between widths |
| `hub_probe.mjs` | A Hub link with a fragment opens that view in the Space's iframe |
| `live_probe.mjs` | The live trial explorer's requests and console errors, at a glance |
