import ReactQuill from 'react-quill'
import 'react-quill/dist/quill.snow.css'

const TOOLBAR = [
  ['bold', 'italic', 'underline'],
  [{ list: 'ordered' }, { list: 'bullet' }],
  ['clean'],
]

export default function RichTextEditor({ value, onChange, placeholder, height = 200 }) {
  return (
    <div style={{ marginBottom: height > 200 ? 42 : 42 }}>
      <ReactQuill
        theme="snow"
        value={value || ''}
        onChange={onChange}
        modules={{ toolbar: TOOLBAR }}
        placeholder={placeholder}
        style={{ height }}
      />
    </div>
  )
}
