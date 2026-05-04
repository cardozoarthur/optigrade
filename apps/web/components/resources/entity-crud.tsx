"use client";

import React, { ReactNode, useEffect, useMemo, useState } from "react";
import { AnimatePresence, motion } from "framer-motion";
import { Loader2, Pencil, Plus, Search, Trash2, X } from "lucide-react";
import type { LucideIcon } from "lucide-react";
import { PageHeader } from "@/components/shell/page-header";
import { Field, IconButton, Panel, PrimaryButton, inputClass } from "@/components/ui";

export type EntityColumn<T> = {
  header: string;
  render: (item: T) => ReactNode;
};

type EntityCrudPageProps<T extends { id: string }, F> = {
  title: string;
  subtitle: string;
  icon: LucideIcon;
  addLabel: string;
  emptyLabel?: string;
  load: () => Promise<T[]>;
  create: (form: F) => Promise<unknown>;
  update: (item: T, form: F) => Promise<unknown>;
  remove: (item: T) => Promise<unknown>;
  columns: EntityColumn<T>[];
  initialForm: () => F;
  formFromItem: (item: T) => F;
  searchText: (item: T) => string;
  itemTitle: (item: T) => string;
  renderForm: (form: F, setForm: React.Dispatch<React.SetStateAction<F>>, mode: "create" | "edit") => ReactNode;
};

export function EntityCrudPage<T extends { id: string }, F>({
  title,
  subtitle,
  icon,
  addLabel,
  emptyLabel = "Nenhum registro encontrado.",
  load,
  create,
  update,
  remove,
  columns,
  initialForm,
  formFromItem,
  searchText,
  itemTitle,
  renderForm
}: EntityCrudPageProps<T, F>) {
  const [items, setItems] = useState<T[]>([]);
  const [query, setQuery] = useState("");
  const [form, setForm] = useState<F>(() => initialForm());
  const [editing, setEditing] = useState<T | null>(null);
  const [open, setOpen] = useState(false);
  const [busy, setBusy] = useState(false);
  const [error, setError] = useState<string | null>(null);

  const filtered = useMemo(() => {
    const normalized = query.trim().toLowerCase();
    if (!normalized) return items;
    return items.filter((item) => searchText(item).toLowerCase().includes(normalized));
  }, [items, query, searchText]);

  async function reload() {
    setError(null);
    setItems(await load());
  }

  useEffect(() => {
    reload().catch((reason: unknown) => setError(errorMessage(reason)));
  }, []);

  function openCreate() {
    setEditing(null);
    setForm(initialForm());
    setError(null);
    setOpen(true);
  }

  function openEdit(item: T) {
    setEditing(item);
    setForm(formFromItem(item));
    setError(null);
    setOpen(true);
  }

  async function submit(event: React.FormEvent<HTMLFormElement>) {
    event.preventDefault();
    setBusy(true);
    setError(null);
    try {
      if (editing) {
        await update(editing, form);
      } else {
        await create(form);
      }
      setOpen(false);
      await reload();
    } catch (reason) {
      setError(errorMessage(reason));
    } finally {
      setBusy(false);
    }
  }

  async function deleteItem(item: T) {
    if (!window.confirm(`Remover ${itemTitle(item)}?`)) return;
    setBusy(true);
    setError(null);
    try {
      await remove(item);
      await reload();
    } catch (reason) {
      setError(errorMessage(reason));
    } finally {
      setBusy(false);
    }
  }

  return (
    <>
      <PageHeader
        icon={icon}
        title={title}
        subtitle={subtitle}
        actions={
          <PrimaryButton onClick={openCreate}>
            <span className="inline-flex items-center gap-2">
              <Plus size={16} />
              {addLabel}
            </span>
          </PrimaryButton>
        }
      />
      <div className="mx-auto grid max-w-7xl gap-4 px-4 py-5 md:px-5">
        {error ? (
          <div className="rounded-md border border-rose/30 bg-rose/10 px-4 py-3 text-sm text-rose">{error}</div>
        ) : null}

        <Panel className="p-3">
          <div className="flex flex-col gap-3 sm:flex-row sm:items-center sm:justify-between">
            <label className="focus-within:ring-lake/30 flex h-10 w-full items-center gap-2 rounded-md border border-slateLine bg-white px-3 text-sm transition focus-within:ring-2 sm:max-w-md">
              <Search size={16} className="text-slate-500" />
              <input
                value={query}
                onChange={(event) => setQuery(event.target.value)}
                className="min-w-0 flex-1 bg-transparent outline-none"
                placeholder="Buscar"
              />
            </label>
            <span className="text-sm text-slate-600">
              {filtered.length} de {items.length} registros
            </span>
          </div>
        </Panel>

        <Panel className="hidden overflow-hidden p-0 lg:block">
          <div className="overflow-x-auto">
            <table className="w-full min-w-[820px] border-collapse text-left text-sm">
              <thead className="bg-slate-50 text-xs uppercase text-slate-500">
                <tr>
                  {columns.map((column) => (
                    <th key={column.header} className="border-b border-slateLine px-4 py-3 font-semibold">
                      {column.header}
                    </th>
                  ))}
                  <th className="w-28 border-b border-slateLine px-4 py-3 text-right font-semibold">Ações</th>
                </tr>
              </thead>
              <tbody>
                {filtered.map((item) => (
                  <tr key={item.id} className="border-b border-slateLine last:border-0 hover:bg-slate-50/70">
                    {columns.map((column) => (
                      <td key={column.header} className="px-4 py-3 align-top">
                        {column.render(item)}
                      </td>
                    ))}
                    <td className="px-4 py-3">
                      <div className="flex justify-end gap-2">
                        <IconButton icon={Pencil} label="Editar" onClick={() => openEdit(item)} />
                        <IconButton icon={Trash2} label="Remover" onClick={() => deleteItem(item)} disabled={busy} />
                      </div>
                    </td>
                  </tr>
                ))}
              </tbody>
            </table>
          </div>
          {filtered.length === 0 ? <EmptyState label={emptyLabel} /> : null}
        </Panel>

        <div className="grid gap-3 lg:hidden">
          {filtered.map((item) => (
            <motion.article
              key={item.id}
              layout
              className="rounded-lg border border-slateLine bg-white p-4 shadow-panel"
            >
              <div className="flex items-start justify-between gap-3">
                <h2 className="min-w-0 text-base font-semibold">{itemTitle(item)}</h2>
                <div className="flex shrink-0 gap-2">
                  <IconButton icon={Pencil} label="Editar" onClick={() => openEdit(item)} />
                  <IconButton icon={Trash2} label="Remover" onClick={() => deleteItem(item)} disabled={busy} />
                </div>
              </div>
              <dl className="mt-3 grid gap-2 text-sm">
                {columns.slice(1).map((column) => (
                  <div key={column.header} className="grid grid-cols-[110px_1fr] gap-2">
                    <dt className="text-xs font-semibold uppercase text-slate-500">{column.header}</dt>
                    <dd className="min-w-0 text-slate-700">{column.render(item)}</dd>
                  </div>
                ))}
              </dl>
            </motion.article>
          ))}
          {filtered.length === 0 ? <EmptyState label={emptyLabel} /> : null}
        </div>
      </div>

      <AnimatePresence>
        {open ? (
          <motion.div
            className="fixed inset-0 z-50 grid place-items-end bg-ink/35 p-0 backdrop-blur-sm sm:place-items-center sm:p-4"
            initial={{ opacity: 0 }}
            animate={{ opacity: 1 }}
            exit={{ opacity: 0 }}
          >
            <motion.section
              initial={{ opacity: 0, y: 24, scale: 0.98 }}
              animate={{ opacity: 1, y: 0, scale: 1 }}
              exit={{ opacity: 0, y: 24, scale: 0.98 }}
              transition={{ duration: 0.18, ease: "easeOut" }}
              className="max-h-[92vh] w-full overflow-hidden rounded-t-lg bg-white shadow-panel sm:max-w-3xl sm:rounded-lg"
            >
              <div className="flex items-center justify-between gap-3 border-b border-slateLine px-4 py-3">
                <div>
                  <p className="text-xs font-semibold uppercase tracking-normal text-lake">
                    {editing ? "Editar registro" : "Novo registro"}
                  </p>
                  <h2 className="text-lg font-semibold">{editing ? itemTitle(editing) : addLabel}</h2>
                </div>
                <IconButton icon={X} label="Fechar" onClick={() => setOpen(false)} disabled={busy} />
              </div>
              <form onSubmit={submit} className="grid max-h-[calc(92vh-68px)] gap-4 overflow-y-auto p-4">
                {renderForm(form, setForm, editing ? "edit" : "create")}
                <div className="sticky bottom-0 -mx-4 -mb-4 flex justify-end gap-2 border-t border-slateLine bg-white px-4 py-3">
                  <button
                    type="button"
                    onClick={() => setOpen(false)}
                    disabled={busy}
                    className="focus-ring h-10 rounded-md border border-slateLine px-4 text-sm font-semibold hover:border-lake disabled:opacity-50"
                  >
                    Cancelar
                  </button>
                  <PrimaryButton type="submit" disabled={busy}>
                    <span className="inline-flex items-center gap-2">
                      {busy ? <Loader2 size={16} className="animate-spin" /> : null}
                      Salvar
                    </span>
                  </PrimaryButton>
                </div>
              </form>
            </motion.section>
          </motion.div>
        ) : null}
      </AnimatePresence>
    </>
  );
}

export function TextInput({
  label,
  value,
  onChange,
  type = "text",
  required,
  placeholder,
  min,
  max
}: {
  label: string;
  value: string | number;
  onChange: (value: string) => void;
  type?: "text" | "email" | "number" | "time";
  required?: boolean;
  placeholder?: string;
  min?: number;
  max?: number;
}) {
  return (
    <Field label={label}>
      <input
        className={inputClass}
        value={value}
        onChange={(event) => onChange(event.target.value)}
        type={type}
        required={required}
        placeholder={placeholder}
        min={min}
        max={max}
      />
    </Field>
  );
}

export function SelectInput({
  label,
  value,
  onChange,
  options,
  required
}: {
  label: string;
  value: string;
  onChange: (value: string) => void;
  options: Array<{ value: string; label: string }>;
  required?: boolean;
}) {
  return (
    <Field label={label}>
      <select className={inputClass} value={value} onChange={(event) => onChange(event.target.value)} required={required}>
        {options.map((option) => (
          <option key={option.value} value={option.value}>
            {option.label}
          </option>
        ))}
      </select>
    </Field>
  );
}

export function CheckboxInput({
  label,
  checked,
  onChange
}: {
  label: string;
  checked: boolean;
  onChange: (value: boolean) => void;
}) {
  return (
    <label className="flex h-10 items-center gap-2 rounded-md border border-slateLine bg-white px-3 text-sm font-semibold">
      <input type="checkbox" checked={checked} onChange={(event) => onChange(event.target.checked)} />
      {label}
    </label>
  );
}

function EmptyState({ label }: { label: string }) {
  return (
    <div className="rounded-lg border border-dashed border-slateLine bg-white px-4 py-8 text-center text-sm text-slate-600">
      {label}
    </div>
  );
}

function errorMessage(reason: unknown) {
  return reason instanceof Error ? reason.message : String(reason);
}
