/* NASA/Tycho cube textures from Cesium; see assets/skybox/README.md. */
(() => {
  const surface = document.createElement('canvas');
  const gl = surface.getContext('webgl', {alpha:false, antialias:false, preserveDrawingBuffer:true});
  let ready = false, program, angles, aspect, lastFrame = '';
  const redraw = () => { if (typeof draw === 'function') draw(); };
  window.drawAtlasBackdrop = (context, {w,h,yaw,pitch}) => {
    if (!ready || !w || !h) return false;
    const ratio = Math.min(window.devicePixelRatio || 1, 2);
    const width = Math.max(1, Math.round(w*ratio)), height = Math.max(1, Math.round(h*ratio));
    const frame = `${width}:${height}:${yaw}:${pitch}`;
    if (frame !== lastFrame) {
      if (surface.width !== width || surface.height !== height) { surface.width=width; surface.height=height; }
      gl.viewport(0,0,width,height);
      gl.useProgram(program);
      gl.uniform2f(angles,yaw,pitch);
      gl.uniform1f(aspect,w/h);
      gl.drawArrays(gl.TRIANGLES,0,6);
      lastFrame=frame;
    }
    context.drawImage(surface,0,0,w,h);
    return true;
  };
  if (!gl) return; // app.js supplies fallback stars on browsers without WebGL.
  surface.addEventListener('webglcontextlost', event => { event.preventDefault(); ready=false; redraw(); });
  surface.addEventListener('webglcontextrestored', () => initialize());
  function shader(type,source) {
    const item=gl.createShader(type);
    gl.shaderSource(item,source); gl.compileShader(item);
    if (!gl.getShaderParameter(item,gl.COMPILE_STATUS)) throw new Error(gl.getShaderInfoLog(item));
    return item;
  }
  async function initialize() {
    ready=false; lastFrame='';
    try {
      program=gl.createProgram();
      const vertex=shader(gl.VERTEX_SHADER,`
        attribute vec2 position; varying vec2 uv;
        void main(){uv=position; gl_Position=vec4(position,0.0,1.0);}
      `);
      const fragment=shader(gl.FRAGMENT_SHADER,`
        precision mediump float;
        varying vec2 uv; uniform samplerCube stars; uniform vec2 angles; uniform float aspect;
        void main(){
          // Fixed field of view: distant stars rotate but never pan or zoom.
          vec3 ray=normalize(vec3(uv.x*aspect*0.57735,uv.y*0.57735,1.0));
          float cp=cos(angles.y),sp=sin(angles.y),cy=cos(angles.x),sy=sin(angles.x);
          ray=vec3(ray.x,cp*ray.y+sp*ray.z,-sp*ray.y+cp*ray.z);
          ray=vec3(cy*ray.x+sy*ray.z,ray.y,-sy*ray.x+cy*ray.z);
          gl_FragColor=vec4(textureCube(stars,ray).rgb,1.0);
        }
      `);
      gl.attachShader(program,vertex); gl.attachShader(program,fragment); gl.linkProgram(program);
      gl.deleteShader(vertex); gl.deleteShader(fragment);
      if (!gl.getProgramParameter(program,gl.LINK_STATUS)) throw new Error(gl.getProgramInfoLog(program));
      gl.useProgram(program);
      const buffer=gl.createBuffer(); gl.bindBuffer(gl.ARRAY_BUFFER,buffer);
      gl.bufferData(gl.ARRAY_BUFFER,new Float32Array([-1,-1,1,-1,-1,1,-1,1,1,-1,1,1]),gl.STATIC_DRAW);
      const position=gl.getAttribLocation(program,'position');
      gl.enableVertexAttribArray(position); gl.vertexAttribPointer(position,2,gl.FLOAT,false,0,0);
      angles=gl.getUniformLocation(program,'angles'); aspect=gl.getUniformLocation(program,'aspect');
      const texture=gl.createTexture();
      const images=await Promise.all(['px','mx','py','my','pz','mz'].map(face=>new Promise((resolve,reject)=>{
        const image=new Image(); image.onload=()=>resolve(image);
        image.onerror=()=>reject(new Error(`Missing skybox face: ${face}`));
        image.src=`assets/skybox/tycho2t3_80_${face}.jpg`;
      })));
      if (gl.isContextLost()) return;
      gl.activeTexture(gl.TEXTURE0); gl.bindTexture(gl.TEXTURE_CUBE_MAP,texture);
      gl.pixelStorei(gl.UNPACK_FLIP_Y_WEBGL,true);
      images.forEach((image,index)=>gl.texImage2D(gl.TEXTURE_CUBE_MAP_POSITIVE_X+index,0,gl.RGB,gl.RGB,gl.UNSIGNED_BYTE,image));
      gl.texParameteri(gl.TEXTURE_CUBE_MAP,gl.TEXTURE_MIN_FILTER,gl.LINEAR);
      gl.texParameteri(gl.TEXTURE_CUBE_MAP,gl.TEXTURE_MAG_FILTER,gl.LINEAR);
      gl.texParameteri(gl.TEXTURE_CUBE_MAP,gl.TEXTURE_WRAP_S,gl.CLAMP_TO_EDGE);
      gl.texParameteri(gl.TEXTURE_CUBE_MAP,gl.TEXTURE_WRAP_T,gl.CLAMP_TO_EDGE);
      gl.uniform1i(gl.getUniformLocation(program,'stars'),0);
      if (gl.getError() !== gl.NO_ERROR) throw new Error('Skybox texture upload failed');
      ready=true; redraw();
    } catch(error) { console.warn('Atlas skybox unavailable; using fallback stars.',error); redraw(); }
  }
  initialize();
})();

