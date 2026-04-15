import Editor, { OnMount } from '@monaco-editor/react'

export default function CodeEditor({ code, onChange }: { code: string; onChange?: (value: string) => void }) {
  const handleEditorDidMount: OnMount = (editor, monaco) => {
    // Define a custom theme that matches the project's aesthetics
    monaco.editor.defineTheme('trinity-dark', {
      base: 'vs-dark',
      inherit: true,
      rules: [
        { token: 'comment', foreground: '6272a4', fontStyle: 'italic' },
        { token: 'keyword', foreground: 'ff79c6', fontStyle: 'bold' }, // Neon Pink
        { token: 'string', foreground: 'f1fa8c' }, // Yellow
        { token: 'number', foreground: 'bd93f9' }, // Purple
        { token: 'identifier', foreground: 'f8f8f2' },
        { token: 'type', foreground: '8be9fd' }, // Cyan
        { token: 'function', foreground: '50fa7b', fontStyle: 'bold' }, // Neon Green
        { token: 'operator', foreground: 'ff79c6' },
      ],
      colors: {
        'editor.background': '#0d0d1a', // Deep Cyber Indigo
        'editor.foreground': '#f8f8f2',
        'editorLineNumber.foreground': '#4d4d70',
        'editorLineNumber.activeForeground': '#bd93f9',
        'editor.lineHighlightBackground': '#bd93f915',
        'editor.selectionBackground': '#44475a88',
        'editor.inactiveSelectionBackground': '#44475a44',
        'editorCursor.foreground': '#ff79c6',
        'editor.indentGuide.background': '#2d2d44',
        'editor.indentGuide.activeBackground': '#bd93f9',
      }
    });
    monaco.editor.setTheme('trinity-dark');
  };

  return (
    <Editor
      height="500px"
      defaultLanguage="python"
      value={code || ''}
      onMount={handleEditorDidMount}
      onChange={(value) => onChange?.(value || "")}
      options={{
        readOnly: false,
        minimap: { enabled: false },
        fontSize: 13,
        fontFamily: "'JetBrains Mono', 'Fira Code', monospace",
        lineNumbers: 'on',
        folding: true,
        wordWrap: 'on',
        scrollBeyondLastLine: false,
        padding: { top: 20, bottom: 20 },
        smoothScrolling: true,
        cursorSmoothCaretAnimation: "on",
        renderLineHighlight: "all",
      }}
    />
  )
}