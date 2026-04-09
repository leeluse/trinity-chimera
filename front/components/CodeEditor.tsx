import Editor from '@monaco-editor/react'

export default function CodeEditor({ code }: { code: string }) {
  return (
    <Editor
      height="500px"
      defaultLanguage="python"
      value={code || '// No strategy code available'}
      theme="vs-dark"
      options={{
        readOnly: true,
        minimap: { enabled: false },
        fontSize: 13,
        lineNumbers: 'on',
        folding: true,
        wordWrap: 'on'
      }}
    />
  )
}