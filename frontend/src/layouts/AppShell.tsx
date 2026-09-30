import { BookOpen, LayoutDashboard, Library, Moon, ScrollText, Sun } from "lucide-react";
import { NavLink, Outlet } from "react-router-dom";
import { useEffect, useState } from "react";

const links = [
  { to: "/", label: "Dashboard", icon: LayoutDashboard, end: true },
  { to: "/stories", label: "Stories", icon: Library, end: false },
  { to: "/demo", label: "Demo", icon: BookOpen, end: false },
];

export function AppShell() {
  const [dark, setDark] = useState(() => localStorage.getItem("theme") !== "light");

  useEffect(() => {
    document.documentElement.classList.toggle("dark", dark);
    document.body.className = dark
      ? "bg-zinc-950 text-zinc-100"
      : "bg-stone-50 text-zinc-900";
    localStorage.setItem("theme", dark ? "dark" : "light");
  }, [dark]);

  return (
    <div className="min-h-screen md:grid md:grid-cols-[240px_1fr]">
      <aside className="border-b border-zinc-800 bg-zinc-950/90 px-4 py-5 md:min-h-screen md:border-b-0 md:border-r">
        <div className="mb-6">
          <p className="text-xs uppercase tracking-[0.2em] text-amber-300/80">Writers room</p>
          <h1 className="font-display text-2xl text-zinc-50">Serial Story</h1>
        </div>
        <nav className="flex gap-2 md:flex-col">
          {links.map((link) => (
            <NavLink
              key={link.to}
              to={link.to}
              end={link.end}
              className={({ isActive }) =>
                `flex items-center gap-2 rounded-lg px-3 py-2 text-sm ${
                  isActive ? "bg-amber-400 text-zinc-950" : "text-zinc-300 hover:bg-zinc-800"
                }`
              }
            >
              <link.icon size={16} />
              {link.label}
            </NavLink>
          ))}
        </nav>
        <button
          className="mt-6 inline-flex items-center gap-2 text-xs text-zinc-400"
          onClick={() => setDark((value) => !value)}
        >
          {dark ? <Sun size={14} /> : <Moon size={14} />}
          {dark ? "Light mode" : "Dark mode"}
        </button>
        <p className="mt-6 hidden items-center gap-2 text-xs text-zinc-500 md:flex">
          <ScrollText size={14} /> Memory and logs live inside each story.
        </p>
      </aside>
      <main className="px-4 py-6 md:px-8">
        <Outlet />
      </main>
    </div>
  );
}
