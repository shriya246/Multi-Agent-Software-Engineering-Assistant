import { Link } from "react-router-dom";

export function NotFoundPage() {
  return (
    <section className="space-y-4">
      <div className="rounded-xl border border-slate-800 bg-slate-900 p-6 shadow-soft">
        <h1 className="text-2xl font-semibold text-slate-50">Page not found</h1>
        <p className="mt-2 text-sm text-slate-300">
          The page you asked for does not exist in this scaffold.
        </p>
        <Link
          to="/"
          className="mt-4 inline-flex rounded-md bg-sky-400 px-4 py-2 text-sm font-medium text-slate-950"
        >
          Return home
        </Link>
      </div>
    </section>
  );
}
