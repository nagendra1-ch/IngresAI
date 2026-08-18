import React from 'react';

/**
 * MarkdownRenderer — Shared AI response text formatter.
 * Parses a rich subset of markdown:
 * - Bold (**text**) and Italic (*text*)
 * - Headers (#, ##, ###)
 * - Blockquotes (> quote)
 * - Bullet lists (- or *)
 * - Tables (| col1 | col2 |)
 * - Paragraphs
 */
const MarkdownRenderer = ({ text, fontSize = '0.95rem', lineHeight = '1.6' }) => {
  if (!text) return null;

  // Helper to apply bold and italic styling
  const formatText = (txt) => {
    if (!txt) return '';
    let formatted = txt;
    formatted = formatted.replace(/\*\*(.*?)\*\*/g, '<strong>$1</strong>');
    formatted = formatted.replace(/\*(.*?)\*/g, '<em>$1</em>');
    return formatted;
  };

  // Parser: processes line-by-line into structured blocks
  const parseMarkdown = (rawText) => {
    const lines = rawText.split('\n');
    const blocks = [];
    let i = 0;

    while (i < lines.length) {
      const line = lines[i];
      const trimmed = line.trim();

      // 1. Skip/preserve empty lines
      if (trimmed === '') {
        blocks.push({ type: 'break' });
        i++;
        continue;
      }

      // 2. Headers
      if (trimmed.startsWith('#')) {
        const match = trimmed.match(/^(#{1,6})\s+(.*)$/);
        if (match) {
          blocks.push({
            type: 'header',
            level: match[1].length,
            content: match[2],
          });
          i++;
          continue;
        }
      }

      // 3. Blockquotes
      if (trimmed.startsWith('>')) {
        const content = trimmed.replace(/^>\s*/, '');
        blocks.push({ type: 'quote', content });
        i++;
        continue;
      }

      // 4. Bullet lists
      if (trimmed.startsWith('- ') || trimmed.startsWith('* ')) {
        const items = [];
        while (i < lines.length && (lines[i].trim().startsWith('- ') || lines[i].trim().startsWith('* '))) {
          items.push(lines[i].trim().replace(/^[-*]\s+/, ''));
          i++;
        }
        blocks.push({ type: 'list', items });
        continue;
      }

      // 5. Tables
      if (trimmed.startsWith('|')) {
        const tableLines = [];
        while (i < lines.length && lines[i].trim().startsWith('|')) {
          tableLines.push(lines[i].trim());
          i++;
        }

        if (tableLines.length >= 1) {
          const parsedRows = tableLines.map((row) => {
            const cleanRow = row.replace(/^\||\|$/g, '');
            return cleanRow.split('|').map((cell) => cell.trim());
          });

          let hasSeparator = false;
          if (parsedRows.length > 1) {
            const secondRow = parsedRows[1];
            hasSeparator = secondRow.every((cell) => /^[:-]+$/.test(cell) || cell === '');
          }

          let headers = [];
          let rows = [];
          if (hasSeparator) {
            headers = parsedRows[0];
            rows = parsedRows.slice(2);
          } else {
            rows = parsedRows;
          }

          blocks.push({ type: 'table', headers, rows });
          continue;
        }
      }

      // 6. Paragraph
      blocks.push({ type: 'paragraph', content: line });
      i++;
    }

    return blocks;
  };

  const blocks = parseMarkdown(text);

  return (
    <div style={{ wordBreak: 'break-word' }}>
      {blocks.map((block, idx) => {
        switch (block.type) {
          case 'break':
            return <div key={idx} style={{ height: '8px' }} />;

          case 'header': {
            const style = {
              color: 'var(--text-main)',
              marginTop: '16px',
              marginBottom: '8px',
              fontWeight: '600',
            };
            if (block.level === 1) return <h1 key={idx} style={{ ...style, fontSize: '1.4rem' }} dangerouslySetInnerHTML={{ __html: formatText(block.content) }} />;
            if (block.level === 2) return <h2 key={idx} style={{ ...style, fontSize: '1.2rem' }} dangerouslySetInnerHTML={{ __html: formatText(block.content) }} />;
            return <h3 key={idx} style={{ ...style, fontSize: '1.05rem' }} dangerouslySetInnerHTML={{ __html: formatText(block.content) }} />;
          }

          case 'quote':
            return (
              <blockquote
                key={idx}
                style={{
                  borderLeft: '3px solid var(--primary-color)',
                  paddingLeft: '12px',
                  color: 'var(--text-muted)',
                  fontStyle: 'italic',
                  marginTop: '8px',
                  marginBottom: '8px',
                  fontSize,
                  lineHeight,
                }}
                dangerouslySetInnerHTML={{ __html: formatText(block.content) }}
              />
            );

          case 'list':
            return (
              <ul key={idx} style={{ paddingLeft: '20px', marginTop: '4px', marginBottom: '8px' }}>
                {block.items.map((item, itemIdx) => (
                  <li
                    key={itemIdx}
                    style={{ listStyleType: 'disc', fontSize, lineHeight, marginBottom: '4px', color: 'var(--text-main)' }}
                    dangerouslySetInnerHTML={{ __html: formatText(item) }}
                  />
                ))}
              </ul>
            );

          case 'table':
            return (
              <div key={idx} style={{ overflowX: 'auto', marginTop: '12px', marginBottom: '16px', borderRadius: '6px', border: '1px solid var(--border-color)' }}>
                <table style={{ width: '100%', borderCollapse: 'collapse', fontSize: '0.88rem', textAlign: 'left' }}>
                  {block.headers.length > 0 && (
                    <thead>
                      <tr style={{ backgroundColor: 'var(--surface-secondary)', borderBottom: '2px solid var(--border-color)' }}>
                        {block.headers.map((h, hIdx) => (
                          <th key={hIdx} style={{ padding: '10px 12px', fontWeight: '600', color: 'var(--text-main)' }} dangerouslySetInnerHTML={{ __html: formatText(h) }} />
                        ))}
                      </tr>
                    </thead>
                  )}
                  <tbody>
                    {block.rows.map((row, rowIdx) => (
                      <tr key={rowIdx} style={{ borderBottom: '1px solid var(--border-color)', backgroundColor: rowIdx % 2 === 1 ? 'var(--surface-secondary)' : 'transparent' }}>
                        {row.map((cell, cellIdx) => (
                          <td key={cellIdx} style={{ padding: '10px 12px', color: 'var(--text-main)' }} dangerouslySetInnerHTML={{ __html: formatText(cell) }} />
                        ))}
                      </tr>
                    ))}
                  </tbody>
                </table>
              </div>
            );

          case 'paragraph':
          default:
            return (
              <p
                key={idx}
                style={{ marginBottom: '6px', fontSize, lineHeight, color: 'var(--text-main)' }}
                dangerouslySetInnerHTML={{ __html: formatText(block.content) }}
              />
            );
        }
      })}
    </div>
  );
};

export default MarkdownRenderer;
