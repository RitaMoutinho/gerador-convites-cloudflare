import React, { useEffect, useState } from 'react';
import axios from 'axios';
import { FaWandMagicSparkles, FaLink, FaImage, FaCheck, FaSpinner, FaXmark, FaCopy, FaHeart, FaUser } from 'react-icons/fa6';

function slugify(text) {
  return text
    .normalize('NFD').replace(/[̀-ͯ]/g, '')
    .toLowerCase()
    .replace(/[^a-z0-9]+/g, '-')
    .replace(/^-+|-+$/g, '');
}

function App() {
  const [mode, setMode] = useState('create'); // 'create' | 'update'
  const [canvaUrl, setCanvaUrl] = useState('');
  const [nome, setNome] = useState('');
  const [idade, setIdade] = useState('');
  const [existingLink, setExistingLink] = useState('');
  const [image, setImage] = useState(null);
  const [imagePreviewUrl, setImagePreviewUrl] = useState('');
  const [loading, setLoading] = useState(false);
  const [resultUrl, setResultUrl] = useState('');
  const [error, setError] = useState('');
  const [copied, setCopied] = useState(false);

  // Build/revoke an object URL so the chosen image can actually be shown,
  // instead of just a filename + checkmark.
  useEffect(() => {
    if (!image) {
      setImagePreviewUrl('');
      return;
    }
    const objectUrl = URL.createObjectURL(image);
    setImagePreviewUrl(objectUrl);
    return () => URL.revokeObjectURL(objectUrl);
  }, [image]);

  const handleSubmit = async (e) => {
    e.preventDefault();
    if (!canvaUrl) {
      setError('Cole o link do Canva!');
      return;
    }
    if (mode === 'update' && !existingLink) {
      setError('Cole o link do convite já publicado!');
      return;
    }

    setLoading(true);
    setError('');
    setResultUrl('');

    const formData = new FormData();
    formData.append('canvaUrl', canvaUrl);
    if (image) {
      formData.append('previewImage', image);
    }

    const endpoint = mode === 'update' ? 'http://localhost:4000/api/update' : 'http://localhost:4000/api/deploy';
    if (mode === 'update') {
      formData.append('link', existingLink);
    } else {
      if (nome) formData.append('nome', nome);
      if (idade) formData.append('idade', idade);
    }

    try {
      const response = await axios.post(endpoint, formData, {
        headers: { 'Content-Type': 'multipart/form-data' }
      });
      setResultUrl(response.data.url);
    } catch (err) {
      setError(err.response?.data?.error || 'Erro ao gerar o convite. Verifique se o backend está ligado e se o Cloudflare (wrangler) está logado.');
    } finally {
      setLoading(false);
    }
  };

  const handleCopy = async () => {
    await navigator.clipboard.writeText(resultUrl);
    setCopied(true);
    setTimeout(() => setCopied(false), 2000);
  };

  return (
    <div className="min-h-screen bg-slate-950 text-white relative overflow-hidden">
      {/* Ambient background */}
      <div className="pointer-events-none absolute inset-0 bg-gradient-to-br from-slate-950 via-purple-950 to-slate-950" />
      <div className="pointer-events-none absolute -top-40 -left-40 w-[28rem] h-[28rem] bg-purple-600/25 rounded-full blur-3xl animate-float-slow" />
      <div className="pointer-events-none absolute -bottom-40 -right-40 w-[28rem] h-[28rem] bg-pink-600/20 rounded-full blur-3xl animate-float-slow-reverse" />
      <div className="pointer-events-none absolute top-1/3 right-1/4 w-64 h-64 bg-fuchsia-500/10 rounded-full blur-3xl animate-float-slow" />

      <div className="relative min-h-screen flex items-center justify-center p-4 sm:p-8">
        <div className="max-w-5xl w-full grid lg:grid-cols-[1.05fr_1fr] gap-8 lg:gap-12 items-center">

          {/* Left: branding + decorative invite mockup */}
          <div className="hidden lg:flex flex-col gap-8 pr-4">
            <div>
              <div className="inline-flex items-center gap-2 px-3 py-1 rounded-full bg-purple-500/10 border border-purple-500/30 text-xs font-semibold tracking-widest uppercase text-purple-300 mb-6">
                <FaWandMagicSparkles /> Digital
              </div>
              <h1 className="text-4xl xl:text-5xl font-extrabold leading-tight mb-4">
                Transforme seu{' '}
                <span className="text-transparent bg-clip-text bg-gradient-to-r from-purple-400 via-fuchsia-400 to-pink-400">
                  convite do Canva
                </span>{' '}
                em um site no ar.
              </h1>
              <p className="text-slate-400 text-lg leading-relaxed">
                Cole o link, escolha a imagem de compartilhamento e pronto — seu convite ganha um endereço
                próprio, prévia bonita no WhatsApp e carrega rapidinho.
              </p>
            </div>

            {/* Decorative floating invite card */}
            <div className="relative h-64 mt-2">
              <div className="absolute left-4 top-6 w-52 h-64 rounded-3xl bg-gradient-to-br from-slate-800/80 to-slate-900/80 border border-white/10 shadow-2xl rotate-6" />
              <div className="absolute left-16 top-0 w-52 h-64 rounded-3xl bg-gradient-to-br from-purple-600/90 via-fuchsia-600/80 to-pink-600/90 border border-white/10 shadow-2xl shadow-purple-950/60 animate-card-tilt flex flex-col items-center justify-center gap-3 p-6 text-center">
                <FaHeart className="text-3xl text-white/90 animate-sparkle" />
                <p className="font-bold text-lg leading-snug">Você está<br />convidado(a)!</p>
                <div className="w-10 h-[3px] rounded-full bg-white/50" />
                <p className="text-xs text-white/70">seusite.vercel.app</p>
              </div>
              <FaWandMagicSparkles className="absolute -left-2 bottom-2 text-2xl text-purple-300 animate-sparkle" />
              <FaHeart className="absolute right-4 top-2 text-lg text-pink-300 animate-sparkle" style={{ animationDelay: '1s' }} />
            </div>
          </div>

          {/* Right: form card */}
          <div className="w-full">
            <div className="bg-slate-900/60 backdrop-blur-xl p-8 sm:p-10 rounded-3xl shadow-2xl shadow-purple-950/50 border border-white/10">
              <div className="flex items-center gap-4 mb-2 lg:hidden">
                <div className="w-14 h-14 shrink-0 rounded-2xl bg-gradient-to-br from-purple-500/30 to-pink-500/20 flex items-center justify-center border border-purple-500/40">
                  <FaWandMagicSparkles className="text-2xl text-purple-300" />
                </div>
                <div>
                  <h1 className="text-2xl font-bold text-transparent bg-clip-text bg-gradient-to-r from-purple-300 via-pink-300 to-purple-300">
                    Gerador de Convites
                  </h1>
                  <p className="text-sm text-slate-400">Do Canva direto para o ar</p>
                </div>
              </div>
              <p className="hidden lg:block text-xs uppercase tracking-widest text-purple-400/70 font-semibold mb-8">
                Gerador de Convites
              </p>
              <p className="text-xs uppercase tracking-widest text-purple-400/70 font-semibold mb-8 mt-1 lg:hidden">
                Digital
              </p>

              <div className="grid grid-cols-2 gap-2 p-1 rounded-xl bg-slate-950/60 border border-slate-700 mb-6">
                <button
                  type="button"
                  onClick={() => { setMode('create'); setError(''); setResultUrl(''); }}
                  className={`py-2 rounded-lg text-sm font-semibold transition-all ${mode === 'create' ? 'bg-gradient-to-r from-purple-600 to-pink-600 text-white shadow' : 'text-slate-400 hover:text-white'}`}
                >
                  Criar novo
                </button>
                <button
                  type="button"
                  onClick={() => { setMode('update'); setError(''); setResultUrl(''); }}
                  className={`py-2 rounded-lg text-sm font-semibold transition-all ${mode === 'update' ? 'bg-gradient-to-r from-purple-600 to-pink-600 text-white shadow' : 'text-slate-400 hover:text-white'}`}
                >
                  Atualizar existente
                </button>
              </div>

              <form onSubmit={handleSubmit} className="space-y-6">
                {mode === 'update' && (
                  <div>
                    <label className="flex items-center gap-2 text-sm font-medium text-slate-300 mb-2">
                      <FaLink className="text-purple-400" /> Link do convite já publicado
                    </label>
                    <input
                      type="text"
                      placeholder="https://digital-convites.vercel.app/nome-15-123456/"
                      className="w-full bg-slate-950/60 border border-slate-700 rounded-xl px-4 py-3 text-white placeholder:text-slate-600 focus:outline-none focus:ring-2 focus:ring-purple-500 focus:border-transparent transition-all"
                      value={existingLink}
                      onChange={(e) => setExistingLink(e.target.value)}
                      required
                    />
                  </div>
                )}

                <div>
                  <label className="flex items-center gap-2 text-sm font-medium text-slate-300 mb-2">
                    <span className="w-5 h-5 rounded-full bg-purple-500/20 text-purple-300 text-xs flex items-center justify-center font-bold">1</span>
                    <FaLink className="text-purple-400" /> Link {mode === 'update' ? 'atualizado ' : ''}do Canva
                  </label>
                  <input
                    type="url"
                    placeholder="https://seemg.my.canva.site/..."
                    className="w-full bg-slate-950/60 border border-slate-700 rounded-xl px-4 py-3 text-white placeholder:text-slate-600 focus:outline-none focus:ring-2 focus:ring-purple-500 focus:border-transparent transition-all"
                    value={canvaUrl}
                    onChange={(e) => setCanvaUrl(e.target.value)}
                    required
                  />
                </div>

                {mode === 'create' && (
                  <div className="grid grid-cols-2 gap-4">
                    <div>
                      <label className="flex items-center gap-2 text-sm font-medium text-slate-300 mb-2">
                        <span className="w-5 h-5 rounded-full bg-purple-500/20 text-purple-300 text-xs flex items-center justify-center font-bold">2</span>
                        <FaUser className="text-purple-400" /> Nome
                      </label>
                      <input
                        type="text"
                        placeholder="Davi Emanuel"
                        className="w-full bg-slate-950/60 border border-slate-700 rounded-xl px-4 py-3 text-white placeholder:text-slate-600 focus:outline-none focus:ring-2 focus:ring-purple-500 focus:border-transparent transition-all"
                        value={nome}
                        onChange={(e) => setNome(e.target.value)}
                      />
                    </div>
                    <div>
                      <label className="flex items-center gap-2 text-sm font-medium text-slate-300 mb-2">
                        Idade
                      </label>
                      <input
                        type="number"
                        min="0"
                        placeholder="13"
                        className="w-full bg-slate-950/60 border border-slate-700 rounded-xl px-4 py-3 text-white placeholder:text-slate-600 focus:outline-none focus:ring-2 focus:ring-purple-500 focus:border-transparent transition-all"
                        value={idade}
                        onChange={(e) => setIdade(e.target.value)}
                      />
                    </div>
                  </div>
                )}

                {mode === 'create' && (nome || idade) && (
                  <p className="text-xs text-slate-500 -mt-3">
                    Link ficará algo como: <span className="text-purple-300">digital-convites.vercel.app/{[slugify(nome || ''), idade].filter(Boolean).join('-')}-123456/</span>
                  </p>
                )}

                <div>
                  <label className="flex items-center gap-2 text-sm font-medium text-slate-300 mb-2">
                    {mode === 'create' && <span className="w-5 h-5 rounded-full bg-purple-500/20 text-purple-300 text-xs flex items-center justify-center font-bold">3</span>}
                    <FaImage className="text-purple-400" /> Imagem de preview (WhatsApp/Facebook){mode === 'update' ? ' — opcional, mantém a atual se não trocar' : ''}
                  </label>

                  {imagePreviewUrl ? (
                    <div className="relative rounded-xl overflow-hidden border border-slate-700 group">
                      <img
                        src={imagePreviewUrl}
                        alt="Pré-visualização da imagem selecionada"
                        className="w-full h-44 object-cover"
                      />
                      <div className="absolute inset-0 bg-black/40 opacity-0 group-hover:opacity-100 transition-opacity flex items-end p-3">
                        <span className="text-xs text-white/90 flex items-center gap-1 truncate">
                          <FaCheck className="text-green-400 shrink-0" /> {image.name}
                        </span>
                      </div>
                      <button
                        type="button"
                        onClick={() => setImage(null)}
                        className="absolute top-2 right-2 w-7 h-7 rounded-full bg-black/60 hover:bg-red-500/80 flex items-center justify-center transition-colors"
                        aria-label="Remover imagem"
                      >
                        <FaXmark className="text-sm" />
                      </button>
                    </div>
                  ) : (
                    <div className="relative border-2 border-dashed border-slate-700 rounded-xl p-6 text-center hover:border-purple-500 transition-all bg-slate-950/30">
                      <input
                        type="file"
                        accept="image/*"
                        onChange={(e) => setImage(e.target.files[0] || null)}
                        className="absolute inset-0 w-full h-full opacity-0 cursor-pointer"
                      />
                      <div className="text-slate-400">
                        <span className="text-purple-400 font-medium">Clique</span> ou arraste a imagem aqui.
                      </div>
                    </div>
                  )}
                </div>

                {error && (
                  <div className="bg-red-500/10 border border-red-500/50 text-red-400 p-4 rounded-xl text-sm">
                    {error}
                  </div>
                )}

                <button
                  type="submit"
                  disabled={loading}
                  className="w-full bg-gradient-to-r from-purple-600 to-pink-600 hover:from-purple-500 hover:to-pink-500 text-white font-bold py-4 px-6 rounded-xl shadow-lg shadow-purple-950/50 transform transition-all active:scale-95 disabled:opacity-50 disabled:cursor-not-allowed flex justify-center items-center gap-2"
                >
                  {loading ? (
                    <>
                      <FaSpinner className="animate-spin text-xl" />
                      {mode === 'update' ? 'Atualizando...' : 'Processando mágica...'} (pode levar 1 minuto)
                    </>
                  ) : mode === 'update' ? (
                    'Atualizar convite'
                  ) : (
                    'Gerar convite digital'
                  )}
                </button>
              </form>

              {resultUrl && (
                <div className="mt-8 p-6 bg-green-500/10 border border-green-500/30 rounded-2xl text-center animate-fade-in">
                  <h3 className="text-green-400 font-semibold mb-3 flex items-center justify-center gap-2">
                    <FaCheck /> {mode === 'update' ? 'Convite atualizado!' : 'Sucesso! Seu link está pronto:'}
                  </h3>
                  <a
                    href={resultUrl}
                    target="_blank"
                    rel="noreferrer"
                    className="block text-lg text-white font-bold underline decoration-green-400 hover:text-green-400 transition-colors break-all mb-4"
                  >
                    {resultUrl}
                  </a>
                  <button
                    type="button"
                    onClick={handleCopy}
                    className="inline-flex items-center gap-2 text-sm px-4 py-2 rounded-lg bg-white/5 hover:bg-white/10 border border-white/10 transition-colors"
                  >
                    <FaCopy /> {copied ? 'Copiado!' : 'Copiar link'}
                  </button>
                </div>
              )}
            </div>

            <p className="text-center text-xs text-slate-500 mt-6">
              Feito com <FaWandMagicSparkles className="inline text-purple-400" /> por Digital
            </p>
          </div>
        </div>
      </div>
    </div>
  );
}

export default App;
