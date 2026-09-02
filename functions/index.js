// The one piece of the site that has to decide something per request: which
// language a visitor who asked for "/" gets. The application does this in
// Python (app/content.py, negotiate); this is the same rule at the edge, so a
// built site behaves like a served one.
//
// Cloudflare Pages picks this up for "/" on its own. If Functions are not
// deployed, dist/index.html answers instead with a slower version of the same
// decision.

const LANGUAGES = ["pl", "en"];
const DEFAULT_LANGUAGE = "pl";
const COOKIE = "lang";

function fromCookie(header) {
  if (!header) return null;
  for (const part of header.split(";")) {
    const [name, ...rest] = part.trim().split("=");
    if (name === COOKIE) {
      const value = rest.join("=");
      return LANGUAGES.includes(value) ? value : null;
    }
  }
  return null;
}

function fromHeader(header) {
  if (!header) return null;
  let best = null;
  header.split(",").forEach((part, position) => {
    const [tag, ...params] = part.trim().split(";");
    const language = tag.trim().toLowerCase().split("-")[0];
    if (!LANGUAGES.includes(language)) return;
    let quality = 1;
    for (const param of params) {
      const [key, value] = param.trim().split("=");
      if (key.trim().toLowerCase() === "q") {
        const parsed = Number.parseFloat(value);
        quality = Number.isNaN(parsed) ? 0 : parsed;
      }
    }
    // Higher quality wins; equal quality goes to whichever was listed first.
    if (!best || quality > best.quality || (quality === best.quality && position < best.position)) {
      best = { language, quality, position };
    }
  });
  return best && best.language;
}

export function onRequest({ request }) {
  const language =
    fromCookie(request.headers.get("cookie")) ||
    fromHeader(request.headers.get("accept-language")) ||
    DEFAULT_LANGUAGE;

  return new Response(null, {
    status: 302,
    headers: {
      location: `/${language}`,
      // The answer depends on both, so say so rather than let it be cached
      // for the next visitor.
      vary: "Accept-Language, Cookie",
      "cache-control": "no-store",
    },
  });
}
