// Runs only inside a dedicated Web Worker. No host bindings, cookies or file URLs.
const deepFreeze = value => {
  if (value && typeof value === 'object') {
    Object.freeze(value);
    for (const child of Object.values(value)) deepFreeze(child);
  }
  return value;
};
const decode = async encoded => {
  const bytes = Uint8Array.from(atob(encoded), c => c.charCodeAt(0));
  return createImageBitmap(new Blob([bytes]));
};
self.onmessage = async ({data}) => {
  let source;
  const assets = {};
  try {
    const canvas = new OffscreenCanvas(data.input.width, data.input.height);
    const ctx = canvas.getContext('2d', {alpha: false});
    source = await decode(data.source);
    for (const [id, encoded] of Object.entries(data.assets)) assets[id] = await decode(encoded);
    const input = deepFreeze(data.input);
    const helpers = Object.freeze({
      source: (x=0, y=0, w=input.width, h=input.height) => ctx.drawImage(source, x, y, w, h),
      image: (id, x, y, w, h) => {
        if (!assets[id]) throw new Error('Unknown asset: ' + id);
        ctx.drawImage(assets[id], x, y, w, h);
      },
      // Prefix of an explicitly selected contiguous phrase; never reveals future words.
      caption: (start, end, x=input.width/2, y=input.height*.9, size=input.width/28) => {
        if (!Number.isInteger(start) || !Number.isInteger(end) ||
            start < input.segment.start_word || end > input.segment.end_word || start >= end)
          throw new Error('Caption outside assigned paragraph');
        const words = input.words.slice(start, end);
        const visible = words.filter(w => w.start_ms <= input.time_ms).map(w => w.text).join('');
        if (!visible) return;
        ctx.save();
        ctx.font = `${size}px sans-serif`;
        ctx.textAlign = 'center';
        ctx.textBaseline = 'middle';
        ctx.lineWidth = Math.max(1, size/10);
        ctx.strokeStyle = '#111827';
        ctx.fillStyle = '#ffffff';
        ctx.strokeText(visible, x, y, input.width*.9);
        ctx.fillText(visible, x, y, input.width*.9);
        ctx.restore();
      }
    });
    // Source frame is the initial background, so overlays can preserve real footage.
    helpers.source();
    const result = new Function('ctx', 'input', 'helpers', '"use strict";\n' + data.code)(ctx, input, helpers);
    if (result && typeof result.then === 'function') throw new Error('Frame code must be synchronous');
    const blob = await canvas.convertToBlob({type:'image/png'});
    const bytes = new Uint8Array(await blob.arrayBuffer());
    let binary = '';
    for (let i=0; i<bytes.length; i+=8192) binary += String.fromCharCode(...bytes.subarray(i,i+8192));
    self.postMessage({png:btoa(binary)});
  } catch (error) {
    self.postMessage({error: String(error.message || error).slice(0,2000)});
  } finally {
    if (source) source.close();
    for (const image of Object.values(assets)) image.close();
  }
};
