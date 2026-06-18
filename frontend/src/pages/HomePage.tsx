export function HomePage() {
  return (
    <section className="space-y-4">
      <div className="rounded-xl border border-slate-800 bg-slate-900 p-6 shadow-soft">
        <p className="text-sm uppercase tracking-[0.24em] text-sky-300">
          Phase 1 scaffold
        </p>
        <h1 className="mt-2 text-3xl font-semibold text-slate-50">
          CodePilot dashboard shell
        </h1>
        <p className="mt-3 max-w-2xl text-sm leading-6 text-slate-300">
          The product UI lands here in later phases. For now, this shell proves
          routing, state management, styling, and error handling are wired
          together.
        </p>
      </div>
    </section>
  );
}
