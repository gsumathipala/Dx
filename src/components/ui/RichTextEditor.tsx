"use client";

import React, { useRef, useEffect } from 'react';
import { Bold, Italic, List, ListOrdered, Quote, Heading3, Type } from 'lucide-react';

interface RichTextEditorProps {
    value: string;
    onChange: (value: string) => void;
    className?: string;
}

export function RichTextEditor({ value, onChange, className }: RichTextEditorProps) {
    const editorRef = useRef<HTMLDivElement>(null);

    // Sync external changes to internal HTML only if not focused
    useEffect(() => {
        if (editorRef.current && document.activeElement !== editorRef.current && editorRef.current.innerHTML !== value) {
            editorRef.current.innerHTML = value;
        }
    }, [value]);

    const exec = (cmd: string, arg?: string) => {
        document.execCommand(cmd, false, arg);
        editorRef.current?.focus();
        handleInput(); // Force update
    };

    const handleInput = () => {
        if (editorRef.current) {
            onChange(editorRef.current.innerHTML);
        }
    };

    return (
        <div className={`border rounded-md bg-white shadow-sm overflow-hidden flex flex-col ${className}`}>
            <div className="flex flex-wrap gap-1 p-2 border-b bg-slate-50 items-center">
                <ToolbarBtn icon={<Bold size={16} />} onClick={() => exec('bold')} title="Bold" />
                <ToolbarBtn icon={<Italic size={16} />} onClick={() => exec('italic')} title="Italic" />
                <div className="w-px h-6 bg-slate-300 mx-1" />
                <ToolbarBtn icon={<List size={16} />} onClick={() => exec('insertUnorderedList')} title="Bullet List" />
                <ToolbarBtn icon={<ListOrdered size={16} />} onClick={() => exec('insertOrderedList')} title="Numbered List" />
                <div className="w-px h-6 bg-slate-300 mx-1" />
                <ToolbarBtn label="H3" onClick={() => exec('formatBlock', '<h3>')} title="Heading 3" />
                <ToolbarBtn label="P" onClick={() => exec('formatBlock', '<p>')} title="Paragraph" />
                <ToolbarBtn icon={<Quote size={16} />} onClick={() => exec('formatBlock', '<blockquote>')} title="Quote" />
            </div>
            <div
                ref={editorRef}
                className="p-4 flex-1 outline-none prose prose-sm max-w-none overflow-y-auto"
                style={{ minHeight: '150px' }}
                contentEditable
                onInput={handleInput}
                suppressContentEditableWarning
                dangerouslySetInnerHTML={{ __html: value }}
            />
        </div>
    )
}

function ToolbarBtn({ icon, label, onClick, title }: any) {
    return (
        <button
            onClick={(e) => { e.preventDefault(); onClick(); }}
            className="p-1.5 rounded hover:bg-slate-200 text-slate-700 transition-colors font-bold text-xs min-w-[28px] flex items-center justify-center"
            title={title}
            type="button"
        >
            {icon || label}
        </button>
    );
}
