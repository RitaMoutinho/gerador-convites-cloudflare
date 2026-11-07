// Mostra quantas vezes um convite foi aberto.  Uso: node scripts/count.js <slug> [<slug2> ...]
// "0 acessos" tambem aparece quando o convite nao tem contador (a API responde "Key not found").
(async () => {
    for (const s of process.argv.slice(2)) {
        const r = await fetch('https://abacus.jasoncameron.dev/get/digital-convites-rita/' + s).then((x) => x.json()).catch((e) => ({ error: e.message }));
        console.log(s + ': ' + (r.value != null ? r.value + ' acessos' : (r.error === 'Key not found' ? '0 acessos' : JSON.stringify(r))));
    }
})();
