import { ArrowRight, ArrowUpRight, Check, LockKeyhole, Menu, MoveUpRight, Radio, ShieldCheck, X } from 'lucide-react';
import { useState } from 'react';

const BOT_URL = 'https://t.me/BatnaTradesBot';
const CHANNEL_URL = 'https://t.me/BatnaTrades';

function Mark() {
  return (
    <span className="flex h-9 w-9 items-center justify-center rounded-[11px] bg-[#b7e344] text-[#20252e]">
      <svg viewBox="0 0 24 24" fill="none" className="h-[22px] w-[22px]" aria-hidden="true">
        <path d="M4 17.5 9.1 12l3.2 2.8L20 6.5" stroke="currentColor" strokeWidth="2.4" strokeLinecap="square" strokeLinejoin="miter" />
        <path d="M15.5 6.5H20v4.6" stroke="currentColor" strokeWidth="2.4" strokeLinecap="square" />
      </svg>
    </span>
  );
}

function ChartPanel() {
  return (
    <div className="relative mx-auto w-full max-w-[540px] rotate-[-1.2deg]">
      <div className="absolute -inset-5 rounded-[28px] border border-[#20252e]/10" />
      <div className="relative overflow-hidden rounded-[22px] border border-white/10 bg-[#20252e] p-5 text-[#f2f0e8] shadow-[0_32px_80px_-35px_rgba(32,37,46,.55)] sm:p-7">
        <div className="flex items-start justify-between border-b border-white/10 pb-5">
          <div>
            <div className="font-mono text-[10px] uppercase tracking-[.2em] text-white/45">Batna Trades / visual study</div>
            <div className="mt-2 font-display text-lg font-semibold">A clearer view of the market</div>
          </div>
          <div className="rounded-full border border-white/15 px-2.5 py-1.5 font-mono text-[9px] uppercase tracking-[.12em] text-white/50">Illustration</div>
        </div>
        <div className="relative mt-5 flex h-[232px] items-center justify-center overflow-hidden rounded-xl bg-[#252b35]">
          <div className="absolute inset-0 opacity-40" style={{ backgroundImage: 'radial-gradient(circle at 50% 50%, rgba(183,227,68,.15) 0, transparent 54%), linear-gradient(rgba(255,255,255,.035) 1px, transparent 1px), linear-gradient(90deg, rgba(255,255,255,.035) 1px, transparent 1px)', backgroundSize: 'auto, 32px 32px, 32px 32px' }} />
          <svg viewBox="0 0 440 220" preserveAspectRatio="none" className="absolute inset-0 h-full w-full">
            <ellipse cx="220" cy="110" rx="185" ry="71" fill="none" stroke="rgba(242,240,232,.10)" strokeWidth="1" />
            <ellipse cx="220" cy="110" rx="143" ry="55" fill="none" stroke="rgba(242,240,232,.12)" strokeWidth="1" transform="rotate(-22 220 110)" />
            <ellipse cx="220" cy="110" rx="98" ry="82" fill="none" stroke="rgba(183,227,68,.32)" strokeWidth="1" transform="rotate(28 220 110)" />
            <path d="M42 148 C105 126 107 62 166 76 C207 86 199 164 246 153 C294 142 280 64 327 70 C359 74 371 104 399 83" fill="none" stroke="#b7e344" strokeWidth="2" opacity=".9" />
            <circle cx="42" cy="148" r="3" fill="#b7e344" /><circle cx="166" cy="76" r="4" fill="#b7e344" />
            <circle cx="246" cy="153" r="4" fill="#b7e344" /><circle cx="327" cy="70" r="4" fill="#b7e344" />
            <circle cx="399" cy="83" r="3" fill="#b7e344" />
          </svg>
          <div className="relative rounded-full border border-[#b7e344]/30 bg-[#20252e]/80 px-4 py-2 font-mono text-[9px] uppercase tracking-[.16em] text-[#d8edaa]">Illustrative visual · not live data</div>
        </div>
        <div className="mt-4 grid grid-cols-3 divide-x divide-white/10 border-t border-white/10 pt-4">
          <div><p className="font-mono text-[9px] uppercase tracking-widest text-white/40">Approach</p><p className="mt-1 font-mono text-sm">Structured</p></div>
          <div className="pl-4"><p className="font-mono text-[9px] uppercase tracking-widest text-white/40">Focus</p><p className="mt-1 font-mono text-sm text-[#b7e344]">Clarity</p></div>
          <div className="pl-4"><p className="font-mono text-[9px] uppercase tracking-widest text-white/40">Platform</p><p className="mt-1 font-mono text-sm">Telegram</p></div>
        </div>
      </div>
      <div className="absolute -bottom-6 -left-5 hidden items-center gap-3 rounded-xl border border-[#20252e]/10 bg-[#f7f6f0] px-4 py-3 shadow-xl sm:flex">
        <span className="flex h-8 w-8 items-center justify-center rounded-lg bg-[#20252e] text-[#b7e344]"><Radio size={15} /></span>
        <span><span className="block font-mono text-[9px] uppercase tracking-widest text-[#767b80]">Signal instructions</span><span className="text-xs font-bold">Shared on Telegram</span></span>
      </div>
    </div>
  );
}

function App() {
  const [menuOpen, setMenuOpen] = useState(false);
  const closeMenu = () => setMenuOpen(false);
  return (
    <main className="min-h-[100dvh] overflow-hidden bg-[#f2f0e8] text-[#20252e]">
      <header className="relative z-20 mx-auto flex max-w-[1320px] items-center justify-between px-5 py-5 sm:px-8 lg:px-12">
        <a href="#top" aria-label="Batna Trades home" className="flex items-center gap-3">
          <Mark /><span className="font-display text-[16px] font-bold tracking-[-.04em]">BATNA<span className="font-medium text-[#767b80]"> TRADES</span></span>
        </a>
        <nav className="hidden items-center gap-9 md:flex">
          <a href="#how-it-works" className="text-[12px] font-semibold text-[#646a70] transition-colors hover:text-[#20252e]">How it works</a>
          <a href="#membership" className="text-[12px] font-semibold text-[#646a70] transition-colors hover:text-[#20252e]">Membership</a>
          <a href={CHANNEL_URL} target="_blank" rel="noreferrer" className="text-[12px] font-semibold text-[#646a70] transition-colors hover:text-[#20252e]">Public channel <ArrowUpRight className="ml-1 inline" size={13} /></a>
        </nav>
        <a href={BOT_URL} target="_blank" rel="noreferrer" className="hidden items-center gap-2 rounded-full bg-[#20252e] px-5 py-3 text-[12px] font-bold text-[#f2f0e8] transition-all hover:bg-[#343b47] hover:translate-y-[-1px] sm:inline-flex">Join Now <ArrowRight size={14} /></a>
        <button type="button" onClick={() => setMenuOpen(!menuOpen)} aria-label={menuOpen ? 'Close menu' : 'Open menu'} className="flex h-10 w-10 items-center justify-center rounded-full border border-[#20252e]/15 md:hidden">{menuOpen ? <X size={18} /> : <Menu size={18} />}</button>
      </header>
      {menuOpen && <div className="absolute left-0 right-0 top-[72px] z-30 border-y border-[#20252e]/10 bg-[#f2f0e8] px-6 py-5 shadow-xl md:hidden">
        <nav className="flex flex-col gap-4 text-sm font-semibold">
          <a onClick={closeMenu} href="#how-it-works">How it works</a><a onClick={closeMenu} href="#membership">Membership</a>
          <a onClick={closeMenu} href={CHANNEL_URL} target="_blank" rel="noreferrer">Public Telegram channel</a>
          <a onClick={closeMenu} href={BOT_URL} target="_blank" rel="noreferrer" className="mt-1 rounded-full bg-[#20252e] px-5 py-3 text-center text-[#f2f0e8]">Join Now</a>
        </nav>
      </div>}

      <section id="top" className="relative mx-auto grid max-w-[1320px] items-center gap-14 px-5 pb-24 pt-12 sm:px-8 sm:pt-20 lg:min-h-[690px] lg:grid-cols-[1.02fr_.98fr] lg:gap-8 lg:px-12 lg:pb-28 lg:pt-10">
        <div className="absolute -left-40 top-28 h-96 w-96 rounded-full bg-[#d9e8a6]/30 blur-3xl" />
        <div className="relative z-10">
          <div className="rise inline-flex items-center gap-2 rounded-full border border-[#20252e]/15 bg-white/40 px-3 py-2 font-mono text-[9px] uppercase tracking-[.18em] text-[#4e555d]">
            <span className="h-1.5 w-1.5 rounded-full bg-[#8dbb22]" /> Crypto signals, on Telegram
          </div>
          <h1 className="rise-2 mt-7 max-w-[720px] font-display text-[clamp(3.8rem,8.8vw,7.8rem)] font-semibold leading-[.88] tracking-[-.085em]">
            Read the<br /><span className="relative inline-block">market<span className="absolute -bottom-[.04em] left-0 -z-10 h-[.22em] w-full bg-[#b7e344]" /></span><br />differently<span className="text-[#a1c53c]">.</span>
          </h1>
          <p className="rise-3 mt-7 max-w-[450px] text-[15px] leading-7 text-[#656b70] sm:text-base">A focused crypto signal membership for traders who value clear setups and a defined plan.</p>
          <div className="rise-3 mt-8 flex flex-col gap-3 sm:flex-row">
            <a href={BOT_URL} target="_blank" rel="noreferrer" className="group inline-flex min-h-14 items-center justify-center gap-7 rounded-full bg-[#b7e344] px-7 text-[13px] font-extrabold text-[#20252e] transition-all hover:-translate-y-0.5 hover:bg-[#c5ee59]">Join Now <span className="flex h-7 w-7 items-center justify-center rounded-full bg-[#20252e] text-[#b7e344] transition-transform group-hover:translate-x-0.5"><ArrowRight size={15} /></span></a>
            <a href={CHANNEL_URL} target="_blank" rel="noreferrer" className="inline-flex min-h-14 items-center justify-center gap-2 rounded-full border border-[#20252e]/20 px-6 text-[13px] font-bold transition-colors hover:bg-white/60">Explore the public channel <ArrowUpRight size={14} /></a>
          </div>
          <div className="mt-7 flex items-center gap-3 font-mono text-[10px] uppercase tracking-[.12em] text-[#777d81]"><LockKeyhole size={13} strokeWidth={1.7} /> Membership $20 USDT / month</div>
        </div>
        <div className="rise-3 relative z-10 pb-5 pt-2 sm:px-4 lg:pb-0 lg:pt-8"><ChartPanel /></div>
      </section>

      <div className="overflow-hidden border-y border-[#20252e]/10 bg-[#e9e7df] py-4">
        <div className="ticker-track flex w-max items-center gap-8 font-mono text-[10px] uppercase tracking-[.17em] text-[#72777b]">
          {Array.from({ length: 2 }, (_, set) => <div key={set} className="flex items-center gap-8 pr-8">{['Structure over noise', 'Signals via Telegram', 'A clear process', 'Built for the process'].map((item) => <span key={item} className="flex items-center gap-8 whitespace-nowrap">{item}<span className="h-1.5 w-1.5 rotate-45 bg-[#9fbd4d]" /></span>)}</div>)}
        </div>
      </div>

      <section className="mx-auto max-w-[1320px] px-5 py-24 sm:px-8 sm:py-32 lg:px-12">
        <div className="grid gap-12 lg:grid-cols-[.7fr_1.3fr] lg:gap-24">
          <div><p className="font-mono text-[10px] uppercase tracking-[.2em] text-[#81867f]">The membership</p><h2 className="mt-5 max-w-[390px] font-display text-4xl font-semibold leading-[1.04] tracking-[-.06em] sm:text-5xl">Less noise.<br />More <span className="text-[#829e2f]">structure.</span></h2></div>
          <div className="grid gap-0 sm:grid-cols-2">
            <article className="border-t border-[#20252e]/15 py-6 sm:pr-9"><span className="font-mono text-[10px] text-[#8a9087]">01 / THE SIGNAL</span><h3 className="mt-5 font-display text-xl font-semibold tracking-[-.04em]">A plan, not a hunch.</h3><p className="mt-3 text-sm leading-6 text-[#707579]">Signals are shared in the private Telegram group with instructions to follow for each setup.</p></article>
            <article className="border-t border-[#20252e]/15 py-6 sm:pl-9"><span className="font-mono text-[10px] text-[#8a9087]">02 / THE FLOW</span><h3 className="mt-5 font-display text-xl font-semibold tracking-[-.04em]">Simple to get started.</h3><p className="mt-3 text-sm leading-6 text-[#707579]">Start with the public channel, then use the Telegram bot to continue with membership.</p></article>
            <article className="border-t border-[#20252e]/15 py-6 sm:pr-9"><span className="font-mono text-[10px] text-[#8a9087]">03 / THE PRICE</span><h3 className="mt-5 font-display text-xl font-semibold tracking-[-.04em]">One clear monthly rate.</h3><p className="mt-3 text-sm leading-6 text-[#707579]">$20 USDT per month. Membership access is handled through the Telegram bot.</p></article>
            <article className="border-t border-[#20252e]/15 py-6 sm:pl-9"><span className="font-mono text-[10px] text-[#8a9087]">04 / THE MINDSET</span><h3 className="mt-5 font-display text-xl font-semibold tracking-[-.04em]">Keep a clear process.</h3><p className="mt-3 text-sm leading-6 text-[#707579]">A focused place to follow the signal instructions shared with members.</p></article>
          </div>
        </div>
      </section>

      <section id="how-it-works" className="relative overflow-hidden bg-[#20252e] px-5 py-24 text-[#f2f0e8] sm:px-8 sm:py-32 lg:px-12">
        <div className="grain absolute inset-0" />
        <div className="relative mx-auto max-w-[1320px]">
          <div className="flex flex-col justify-between gap-8 md:flex-row md:items-end">
            <div><p className="font-mono text-[10px] uppercase tracking-[.2em] text-[#b7e344]">Getting started</p><h2 className="mt-5 max-w-[540px] font-display text-4xl font-semibold leading-[1.03] tracking-[-.06em] sm:text-6xl">Three steps.<br /><span className="text-white/40">Then stay sharp.</span></h2></div>
            <p className="max-w-[310px] text-sm leading-6 text-white/55">The public channel is your first stop. The bot is where you continue toward membership.</p>
          </div>
          <div className="mt-16 grid border-t border-white/15 md:grid-cols-3">
            {[
              { n: '01', title: 'Join the public channel', body: 'Get a feel for Batna Trades and see what is shared publicly.', action: 'Open Telegram channel', href: CHANNEL_URL },
              { n: '02', title: 'Continue with the bot', body: 'Open the Batna Trades bot for membership details and next steps.', action: 'Open the Telegram bot', href: BOT_URL },
              { n: '03', title: 'Follow the plan', body: 'Follow the signal instructions shared in the private group.', action: '', href: '' },
            ].map((step, i) => <article key={step.n} className={`border-b border-white/15 py-7 md:border-b-0 md:py-8 ${i > 0 ? 'md:border-l md:border-white/15 md:pl-8' : ''} ${i < 2 ? 'md:pr-8' : ''}`}>
              <span className="font-mono text-xs text-[#b7e344]">{step.n} <span className="ml-2 text-white/30">/ 03</span></span>
              <h3 className="mt-8 font-display text-2xl font-semibold tracking-[-.04em]">{step.title}</h3><p className="mt-3 max-w-[290px] text-sm leading-6 text-white/50">{step.body}</p>
              {step.action && <a href={step.href} target="_blank" rel="noreferrer" className="mt-7 inline-flex items-center gap-2 text-[11px] font-bold text-[#b7e344] hover:text-white">{step.action}<ArrowUpRight size={13} /></a>}
            </article>)}
          </div>
          <div className="mt-8 flex items-start gap-4 rounded-xl border border-[#b7e344]/25 bg-[#b7e344]/[.07] p-5 sm:items-center sm:px-7">
            <ShieldCheck className="mt-0.5 shrink-0 text-[#b7e344]" size={21} />
            <p className="text-sm leading-6 text-white/80"><strong className="font-bold text-white">Risk rule:</strong> Set each stop-loss so the trade risks no more than 10% of your trading balance, and follow the signal instructions in the private group.</p>
          </div>
        </div>
      </section>

      <section id="membership" className="mx-auto max-w-[1320px] px-5 py-24 sm:px-8 sm:py-32 lg:px-12">
        <div className="grid items-center gap-12 lg:grid-cols-[1fr_.86fr] lg:gap-24">
          <div><p className="font-mono text-[10px] uppercase tracking-[.2em] text-[#81867f]">Straightforward access</p><h2 className="mt-5 max-w-[560px] font-display text-4xl font-semibold leading-[1.02] tracking-[-.065em] sm:text-6xl">Your next step<br />is on Telegram.</h2><p className="mt-6 max-w-[450px] text-sm leading-7 text-[#707579]">Membership is $20 USDT per month. Join through the Batna Trades bot to see the available membership steps. This page does not process payment.</p><a href={BOT_URL} target="_blank" rel="noreferrer" className="mt-8 inline-flex items-center gap-3 rounded-full bg-[#20252e] px-7 py-4 text-[13px] font-extrabold text-[#f2f0e8] transition-all hover:-translate-y-0.5 hover:bg-[#343b47]">Join Now <ArrowRight size={15} /></a></div>
          <div className="relative overflow-hidden rounded-[24px] bg-[#b7e344] p-7 sm:p-10">
            <div className="absolute -right-14 -top-16 h-60 w-60 rounded-full border border-[#20252e]/10" /><div className="absolute -right-2 -top-4 h-36 w-36 rounded-full border border-[#20252e]/10" />
            <div className="relative flex items-center justify-between border-b border-[#20252e]/15 pb-7"><span className="font-mono text-[10px] uppercase tracking-[.19em]">Membership / monthly</span><span className="rounded-full border border-[#20252e]/20 px-3 py-1.5 font-mono text-[9px] uppercase tracking-[.1em]">Telegram</span></div>
            <div className="relative mt-8 flex items-end gap-3"><span className="font-display text-[72px] font-semibold leading-none tracking-[-.09em] sm:text-[92px]">$20</span><span className="mb-2 font-mono text-[11px] uppercase tracking-[.12em]">USDT / month</span></div>
            <div className="relative mt-9 space-y-3 border-t border-[#20252e]/15 pt-6 text-[13px] font-semibold">
              <div className="flex items-center gap-3"><Check size={15} strokeWidth={2.4} /> Telegram-based membership</div>
              <div className="flex items-center gap-3"><Check size={15} strokeWidth={2.4} /> Signal instructions in the private group</div>
              <div className="flex items-center gap-3"><Check size={15} strokeWidth={2.4} /> Clear monthly price</div>
            </div>
            <p className="relative mt-8 border-t border-[#20252e]/15 pt-4 font-mono text-[9px] uppercase leading-5 tracking-[.09em] text-[#20252e]/60">Continue to Telegram for membership details.<br />Payment is not taken on this website.</p>
          </div>
        </div>
      </section>

      <footer className="mx-auto max-w-[1320px] px-5 py-8 sm:px-8 lg:px-12">
        <div className="flex flex-col items-start justify-between gap-6 sm:flex-row sm:items-center">
          <a href="#top" className="flex items-center gap-3"><Mark /><span className="font-display text-[14px] font-bold tracking-[-.04em]">BATNA TRADES</span></a>
          <div className="flex flex-wrap items-center gap-x-6 gap-y-3 text-[11px] font-semibold text-[#697075]"><a href={CHANNEL_URL} target="_blank" rel="noreferrer" className="hover:text-[#20252e]">Public Telegram channel <MoveUpRight size={12} className="ml-1 inline" /></a><a href={BOT_URL} target="_blank" rel="noreferrer" className="hover:text-[#20252e]">Telegram bot <MoveUpRight size={12} className="ml-1 inline" /></a><a href="#membership" className="hover:text-[#20252e]">Membership</a></div>
          <p className="font-mono text-[9px] uppercase tracking-[.12em] text-[#969a98]">Batna Trades</p>
        </div>
        <div className="mt-7 flex flex-col justify-between gap-2 border-t border-[#20252e]/10 pt-5 font-mono text-[9px] uppercase tracking-[.1em] text-[#999d99] sm:flex-row"><span>© {new Date().getFullYear()} Batna Trades</span></div>
      </footer>
    </main>
  );
}

export default App;
