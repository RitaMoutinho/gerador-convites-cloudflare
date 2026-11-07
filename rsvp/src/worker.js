// API da confirmação de presença. Os arquivos estáticos (public/) são servidos pelo próprio Cloudflare;
// só /api/* passa por aqui (ver run_worker_first no wrangler.jsonc).

const MAX_COMPANIONS = 20;

const norm = (s) => String(s).normalize('NFD').replace(/[̀-ͯ]/g, '').toLowerCase().replace(/\s+/g, ' ').trim();

const json = (data, status = 200) =>
  new Response(JSON.stringify(data), {
    status,
    headers: { 'content-type': 'application/json; charset=utf-8', 'cache-control': 'no-store' },
  });

const publicGuest = (g) => ({ id: g.id, name: g.name, label: g.label, kid: !!g.kid, age: g.age });

function isAdmin(req, env) {
  const given = (req.headers.get('authorization') || '').replace(/^Bearer\s+/i, '');
  const real = env.ADMIN_PASSWORD || '';
  if (!real) return true;   // sem senha configurada: painel aberto
  if (given.length !== real.length) return false;
  let diff = 0;
  for (let i = 0; i < real.length; i++) diff |= given.charCodeAt(i) ^ real.charCodeAt(i);
  return diff === 0;
}

async function allGuests(env) {
  const { results } = await env.DB.prepare('SELECT id,name,label,kid,age,norm FROM guests ORDER BY id').all();
  return results;
}

async function search(url, env) {
  const q = norm(url.searchParams.get('q') || '');
  if (q.length < 2) return json({ results: [] });
  const tokens = q.split(' ');
  const hits = (await allGuests(env))
    .filter((g) => tokens.every((t) => g.norm.includes(t)))
    .sort((a, b) => Number(b.norm.startsWith(q)) - Number(a.norm.startsWith(q)) || a.norm.localeCompare(b.norm))
    .slice(0, 8);
  return json({ results: hits.map(publicGuest) });
}

// Dados de um convidado (já escolhido na busca): resposta atual + acompanhantes que ele incluiu.
async function guestInfo(url, env) {
  const id = Number(url.searchParams.get('id'));
  const g = await env.DB.prepare('SELECT id,name,label,kid,age FROM guests WHERE id=?').bind(id).first();
  if (!g) return json({ error: 'Convidado não encontrado.' }, 404);
  const mine = await env.DB.prepare('SELECT status,note FROM responses WHERE guest_id=?').bind(id).first();
  const { results } = await env.DB.prepare(
    `SELECT g.id,g.name,g.label,g.kid,g.age FROM responses r JOIN guests g ON g.id=r.guest_id
     WHERE r.by_id=?1 AND r.guest_id!=?1 AND r.status='yes' ORDER BY g.id`
  ).bind(id).all();
  return json({ guest: publicGuest(g), status: mine ? mine.status : null, note: mine ? mine.note : '', companions: results.map(publicGuest) });
}

async function rsvp(req, env) {
  let body;
  try { body = await req.json(); } catch { return json({ error: 'Pedido inválido.' }, 400); }
  const id = Number(body.guestId);
  const status = body.status;
  if (status !== 'yes' && status !== 'no') return json({ error: 'Escolha se você vai ou não.' }, 400);
  const me = await env.DB.prepare('SELECT id,kid FROM guests WHERE id=?').bind(id).first();
  if (!me) return json({ error: 'Seu nome não está na lista.' }, 400);

  let companionIds = [];
  if (status === 'yes') {
    companionIds = [...new Set((Array.isArray(body.companionIds) ? body.companionIds : []).map(Number))]
      .filter((n) => Number.isInteger(n) && n !== id);
    if (companionIds.length > MAX_COMPANIONS) return json({ error: 'Muitos acompanhantes.' }, 400);
    if (companionIds.length) {
      const { results } = await env.DB.prepare(
        `SELECT id FROM guests WHERE id IN (${companionIds.map(() => '?').join(',')})`
      ).bind(...companionIds).all();
      if (results.length !== companionIds.length) return json({ error: 'Algum acompanhante não está na lista.' }, 400);
    }
  }

  const note = String(body.note || '').trim().slice(0, 500);
  const at = new Date().toISOString();
  const up = env.DB.prepare(
    `INSERT INTO responses (guest_id,status,by_id,note,at) VALUES (?1,?2,?3,?4,?5)
     ON CONFLICT(guest_id) DO UPDATE SET status=?2, by_id=?3, note=?4, at=?5`
  );
  // refazer o envio substitui o grupo anterior desta pessoa
  const ops = [env.DB.prepare('DELETE FROM responses WHERE by_id=?1 AND guest_id!=?1').bind(id)];
  ops.push(up.bind(id, status, id, note || null, at));
  for (const c of companionIds) ops.push(up.bind(c, 'yes', id, null, at));
  await env.DB.batch(ops);
  return json({ ok: true });
}

async function adminData(env) {
  const { results } = await env.DB.prepare(
    `SELECT g.id,g.name,g.label,g.kid,g.age,r.status,r.by_id,r.note,r.at,b.name AS by_name
     FROM guests g LEFT JOIN responses r ON r.guest_id=g.id LEFT JOIN guests b ON b.id=r.by_id ORDER BY g.id`
  ).all();
  return json({ guests: results });
}

async function adminSet(req, env) {
  let body;
  try { body = await req.json(); } catch { return json({ error: 'Pedido inválido.' }, 400); }
  const id = Number(body.id);
  const g = await env.DB.prepare('SELECT id FROM guests WHERE id=?').bind(id).first();
  if (!g) return json({ error: 'Convidado não encontrado.' }, 404);
  if (body.status === null) {
    await env.DB.prepare('DELETE FROM responses WHERE guest_id=?').bind(id).run();
  } else if (body.status === 'yes' || body.status === 'no') {
    await env.DB.prepare(
      `INSERT INTO responses (guest_id,status,by_id,note,at) VALUES (?1,?2,?1,NULL,?3)
       ON CONFLICT(guest_id) DO UPDATE SET status=?2, by_id=?1, at=?3`
    ).bind(id, body.status, new Date().toISOString()).run();
  } else {
    return json({ error: 'Status inválido.' }, 400);
  }
  return json({ ok: true });
}

export default {
  async fetch(req, env) {
    const url = new URL(req.url);
    const p = url.pathname;
    try {
      if (p === '/api/search' && req.method === 'GET') return await search(url, env);
      if (p === '/api/guest' && req.method === 'GET') return await guestInfo(url, env);
      if (p === '/api/rsvp' && req.method === 'POST') return await rsvp(req, env);
      if (p.startsWith('/api/admin/')) {
        if (!isAdmin(req, env)) return json({ error: 'Senha incorreta.' }, 401);
        if (p === '/api/admin/data' && req.method === 'GET') return await adminData(env);
        if (p === '/api/admin/set' && req.method === 'POST') return await adminSet(req, env);
      }
      return json({ error: 'Não encontrado.' }, 404);
    } catch (e) {
      return json({ error: 'Erro no servidor. Tente de novo.' }, 500);
    }
  },
};
