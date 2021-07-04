#version 120

#extension GL_ARB_texture_rectangle : enable
#extension GL_EXT_gpu_shader4 : enable

/*
  Original Lens Distortion Algorithm from SSontech (Syntheyes)
  http://www.ssontech.com/content/lensalg.htm
  
  r2 is radius squared.
  
  r2 = image_aspect*image_aspect*u*u + v*v
  f = 1 + r2*(k + kcube*sqrt(r2))
  u' = f*u
  v' = f*v
 
*/

// Controls 
uniform vec3 param1;
float kCoeff = float(param1.x) * 0.01;
float kCube = float(param1.y) * 0.01;
uniform vec3 param2;
float uShift = float(param2.x) * 0.01;
float vShift = float(param2.y) * 0.01;
float chroma_red = float(param2.z) * 0.01;
uniform vec3 param3;
float chroma_green = float(param3.x) * 0.01;
float chroma_blue = float(param3.y) * 0.01;
bool apply_disto = bool(param1.z);

// Front texture
uniform sampler2DRect image1;
// Matte
uniform sampler2DRect image2;

//int override_w = int(param3.z);
uniform vec3 param4;
//int override_h = int(param4.x);
int override_w = int(gl_TexCoord[0].z);
int override_h = int(gl_TexCoord[0].w);

// THESE DO WORK
float adsk_input1_aspect = float(param4.y) * 1.0;
float samples = param4.z;
vec2 res = gl_TexCoord[0].zw;
float adsk_input1_frameratio = res.x/res.y;
float adsk_result_w = res.x;
float adsk_result_h = res.y;

vec2 jitter2[2] = vec2[](
  vec2( 0.246490,  0.249999),
  vec2(-0.246490, -0.249999)
);
vec2 jitter3[3] = vec2[](
  vec2(-0.373411, -0.250550),
  vec2( 0.256263,  0.368119),
  vec2( 0.117148, -0.117570)
);
vec2 jitter4[4] = vec2[4](
  vec2(-0.208147,  0.353730),
  vec2( 0.203849, -0.353780),
  vec2(-0.292626, -0.149945),
  vec2( 0.296924,  0.149994)
);
vec2 jitter8[8] = vec2[8](
  vec2(-0.334818,  0.435331),
  vec2( 0.286438, -0.393495),
  vec2( 0.459462,  0.141540),
  vec2(-0.414498, -0.192829),
  vec2(-0.183790,  0.082102),
  vec2(-0.079263, -0.317383),
  vec2( 0.102254,  0.299133),
  vec2( 0.164216, -0.054399)
);
vec2 jitter15[15] = vec2[15](
  vec2( 0.285561,  0.188437),
  vec2( 0.360176, -0.065688),
  vec2(-0.111751,  0.275019),
  vec2(-0.055918, -0.215197),
  vec2(-0.080231, -0.470965),
  vec2( 0.138721,  0.409168),
  vec2( 0.384120,  0.458500),
  vec2(-0.454968,  0.134088),
  vec2( 0.179271, -0.331196),
  vec2(-0.307049, -0.364927),
  vec2( 0.105354, -0.010099),
  vec2(-0.154180,  0.021794),
  vec2(-0.370135, -0.116425),
  vec2( 0.451636, -0.300013),
  vec2(-0.370610,  0.387504)
);
vec2 jitter24[24] = vec2[24](
  vec2( 0.030245,  0.136384),
  vec2( 0.018865, -0.348867),
  vec2(-0.350114, -0.472309),
  vec2( 0.222181,  0.149524),
  vec2(-0.393670, -0.266873),
  vec2( 0.404568,  0.230436),
  vec2( 0.098381,  0.465337),
  vec2( 0.462671,  0.442116),
  vec2( 0.400373, -0.212720),
  vec2(-0.409988,  0.263345),
  vec2(-0.115878, -0.001981),
  vec2( 0.348425, -0.009237),
  vec2(-0.464016,  0.066467),
  vec2(-0.138674, -0.468006),
  vec2( 0.144932, -0.022780),
  vec2(-0.250195,  0.150161),
  vec2(-0.181400, -0.264219),
  vec2( 0.196097, -0.234139),
  vec2(-0.311082, -0.078815),
  vec2( 0.268379,  0.366778),
  vec2(-0.040601,  0.327109),
  vec2(-0.234392,  0.354659),
  vec2(-0.003102, -0.154402),
  vec2( 0.297997, -0.417965)
);
vec2 jitter66[66] = vec2[66](
  vec2( 0.266377, -0.218171),
  vec2(-0.170919, -0.429368),
  vec2( 0.047356, -0.387135),
  vec2(-0.430063,  0.363413),
  vec2(-0.221638, -0.313768),
  vec2( 0.124758, -0.197109),
  vec2(-0.400021,  0.482195),
  vec2( 0.247882,  0.152010),
  vec2(-0.286709, -0.470214),
  vec2(-0.426790,  0.004977),
  vec2(-0.361249, -0.104549),
  vec2(-0.040643,  0.123453),
  vec2(-0.189296,  0.438963),
  vec2(-0.453521, -0.299889),
  vec2( 0.408216, -0.457699),
  vec2( 0.328973, -0.101914),
  vec2(-0.055540, -0.477952),
  vec2( 0.194421,  0.453510),
  vec2( 0.404051,  0.224974),
  vec2( 0.310136,  0.419700),
  vec2(-0.021743,  0.403898),
  vec2(-0.466210,  0.248839),
  vec2( 0.341369,  0.081490),
  vec2( 0.124156, -0.016859),
  vec2(-0.461321, -0.176661),
  vec2( 0.013210,  0.234401),
  vec2( 0.174258, -0.311854),
  vec2( 0.294061,  0.263364),
  vec2(-0.114836,  0.328189),
  vec2( 0.041206, -0.106205),
  vec2( 0.079227,  0.345021),
  vec2(-0.109319, -0.242380),
  vec2( 0.425005, -0.332397),
  vec2( 0.009146,  0.015098),
  vec2(-0.339084, -0.355707),
  vec2(-0.224596, -0.189548),
  vec2( 0.083475,  0.117028),
  vec2( 0.295962, -0.334699),
  vec2( 0.452998,  0.025397),
  vec2( 0.206511, -0.104668),
  vec2( 0.447544, -0.096004),
  vec2(-0.108006, -0.002471),
  vec2(-0.380810,  0.130036),
  vec2(-0.242440,  0.186934),
  vec2(-0.200363,  0.070863),
  vec2(-0.344844, -0.230814),
  vec2( 0.408660,  0.345826),
  vec2(-0.233016,  0.305203),
  vec2( 0.158475, -0.430762),
  vec2( 0.486972,  0.139163),
  vec2(-0.301610,  0.009319),
  vec2( 0.282245, -0.458671),
  vec2( 0.482046,  0.443890),
  vec2(-0.121527,  0.210223),
  vec2(-0.477606, -0.424878),
  vec2(-0.083941, -0.121440),
  vec2(-0.345773,  0.253779),
  vec2( 0.234646,  0.034549),
  vec2( 0.394102, -0.210901),
  vec2(-0.312571,  0.397656),
  vec2( 0.200906,  0.333293),
  vec2( 0.018703, -0.261792),
  vec2(-0.209349, -0.065383),
  vec2( 0.076248,  0.478538),
  vec2(-0.073036, -0.355064),
  vec2( 0.145087,  0.221726)
);

float distortion_f(float r) {
    float f = 1 + (r*r)*(kCoeff + kCube * r);
    return f;
}

// Returns the F multiplier for the passed distorted radius
float inverse_f(float r_distorted)
{
    
    // Build a lookup table on the radius, as a fixed-size table.
    // We will use a vec2 since we will store the F (distortion coefficient at this R)
    // and the result of F*radius
    vec2[48] lut;
    
    // Since out LUT is shader-global check if it's been computed alrite
    // Flame has no overflow bbox so we can safely max out at the image edge, plus some cushion
    float max_r = sqrt((adsk_input1_frameratio * adsk_input1_frameratio) + 1) + 1;
    float incr = max_r / 48;
    float lut_r = 0;
    float f;
    for(int i=0; i < 48; i++) {
        f = distortion_f(lut_r);
        lut[i] = vec2(f, lut_r * f);
        lut_r += incr;
    }
    
    float t;
    // Now find the nehgbouring elements
    // only iterate to 46 since we will need
    // 47 as i+1
    for(int i=0; i < 47; i++) {
        if(lut[i].y < r_distorted && lut[i+1].y > r_distorted) {
            // BAM! our distorted radius is between these two
            // get the T interpolant and mix
            t = (r_distorted - lut[i].y) / (lut[i+1].y - lut[i]).y;
            return mix(lut[i].x, lut[i+1].x, t );
        }
    }
    // Rolled off the edge
    return lut[47].x;
}

float aberrate(float f, float chroma)
{
   return f + (f * chroma);
}

vec3 chromaticize_and_invert(float f)
{
   vec3 rgb_f = vec3(aberrate(f, chroma_red), aberrate(f, chroma_green), aberrate(f, chroma_blue));
   // We need to DIVIDE by F when we redistort, and x / y == x * (1 / y)
   if(apply_disto) {
      rgb_f = 1 / rgb_f;
   }
   return rgb_f;
}

void main(void)
{
   vec2 px, uv;
   float f = 1;
   float r = 1;
   
   px = gl_FragCoord.xy;
   
   // Make sure we are still centered
   // and account for overscan
   px.x -= (adsk_result_w - override_w) / 2;
   px.y -= (adsk_result_h - override_h) / 2;
   
   // Push the destination coordinates into the [0..1] range
   uv.x = px.x / override_w;
   uv.y = px.y / override_h;
       
   // And to Syntheyes UV which are [1..-1] on both X and Y
   uv.x = (uv.x *2 ) - 1;
   uv.y = (uv.y *2 ) - 1;
   
   // Add UV shifts
   uv.x += uShift;
   uv.y += vShift;
   
   // Make the X value the aspect value, so that the X coordinates go to [-aspect..aspect]
   uv.x = uv.x * adsk_input1_frameratio;
   
   // Compute the radius
   r = sqrt(uv.x*uv.x + uv.y*uv.y);
   
   // If we are redistorting, account for the oversize plate in the input, assume that
   // the input aspect is the same
   if(apply_disto) {
      r = r / (float(adsk_result_w) / float(override_w));
      f = inverse_f(r);
   } else {
      f = distortion_f(r);
   }
   
   vec2[3] rgb_uvs = vec2[](uv, uv, uv);
   
   // Compute distortions per component
   vec3 rgb_f = chromaticize_and_invert(f);
   
   // Apply the disto coefficients, per component
   rgb_uvs[0] = rgb_uvs[0] * rgb_f.rr;
   rgb_uvs[1] = rgb_uvs[1] * rgb_f.gg;
   rgb_uvs[2] = rgb_uvs[2] * rgb_f.bb;
   
   // Convert all the UVs back to the texture space, per color component
   for(int i=0; i < 3; i++) {
       uv = rgb_uvs[i];
       
       // Back from [-aspect..aspect] to [-1..1]
       uv.x = uv.x / adsk_input1_frameratio;
       
       // Remove UV shifts
       uv.x -= uShift;
       uv.y -= vShift;
       
       // Back to OGL UV
       uv.x = (uv.x + 1) / 2;
       uv.y = (uv.y + 1) / 2;
       
       rgb_uvs[i] = uv;
   }
   
   // Sample the input plate, per component
   vec4 tp = vec4(0.0);
   if (samples < 1) {
     tp.r = texture2DRect(image1, res * rgb_uvs[0]).r;
     tp.g = texture2DRect(image1, res * rgb_uvs[1]).g;
     tp.b = texture2DRect(image1, res * rgb_uvs[2]).b;
     if (rgb_uvs[0].x >= 1.0 || rgb_uvs[0].x < 0.0 || rgb_uvs[0].y >= 1.0 || rgb_uvs[0].y < 0.0) { // Out of bounds
      tp.a += 0.0;
     } else {
      tp.a += texture2DRect(image1, res * rgb_uvs[0]).a;
     }
  } else if (samples < 2) {
    float m = 0.5;
    for(int i=0;i<2;i++)
    {
     tp.r += texture2DRect(image1, res * rgb_uvs[0]+jitter2[i]).r * m;
     tp.g += texture2DRect(image1, res * rgb_uvs[1]+jitter2[i]).g * m;
     tp.b += texture2DRect(image1, res * rgb_uvs[2]+jitter2[i]).b * m;
     if (rgb_uvs[0].x >= 1.0 || rgb_uvs[0].x < 0.0 || rgb_uvs[0].y >= 1.0 || rgb_uvs[0].y < 0.0) { // Out of bounds
      tp.a += 0.0;
     } else {
     tp.a += texture2DRect(image1, res * rgb_uvs[2]+jitter2[i]).a * m;
     }
    }
  } else if (samples < 3) {
    float m = 0.333333;
    for(int i=0;i<3;i++)
    {
     tp.r += texture2DRect(image1, res * rgb_uvs[0]+jitter3[i]).r * m;
     tp.g += texture2DRect(image1, res * rgb_uvs[1]+jitter3[i]).g * m;
     tp.b += texture2DRect(image1, res * rgb_uvs[2]+jitter3[i]).b * m;
     if (rgb_uvs[0].x >= 1.0 || rgb_uvs[0].x < 0.0 || rgb_uvs[0].y >= 1.0 || rgb_uvs[0].y < 0.0) { // Out of bounds
      tp.a += 0.0;
     } else {
     tp.a += texture2DRect(image1, res * rgb_uvs[2]+jitter3[i]).a * m;
     }
    }
  } else if (samples < 4) {
    float m = 0.25;
    for(int i=0;i<4;i++)
    {
     tp.r += texture2DRect(image1, res * rgb_uvs[0]+jitter4[i]).r * m;
     tp.g += texture2DRect(image1, res * rgb_uvs[1]+jitter4[i]).g * m;
     tp.b += texture2DRect(image1, res * rgb_uvs[2]+jitter4[i]).b * m;
     if (rgb_uvs[0].x >= 1.0 || rgb_uvs[0].x < 0.0 || rgb_uvs[0].y >= 1.0 || rgb_uvs[0].y < 0.0) { // Out of bounds
      tp.a += 0.0;
     } else {
     tp.a += texture2DRect(image1, res * rgb_uvs[2]+jitter4[i]).a * m;
     }
    }
  } else if (samples < 5) {
    float m = 0.125;
    for(int i=0;i<8;i++)
    {
     tp.r += texture2DRect(image1, res * rgb_uvs[0]+jitter8[i]).r * m;
     tp.g += texture2DRect(image1, res * rgb_uvs[1]+jitter8[i]).g * m;
     tp.b += texture2DRect(image1, res * rgb_uvs[2]+jitter8[i]).b * m;
     if (rgb_uvs[0].x >= 1.0 || rgb_uvs[0].x < 0.0 || rgb_uvs[0].y >= 1.0 || rgb_uvs[0].y < 0.0) { // Out of bounds
      tp.a += 0.0;
     } else {
     tp.a += texture2DRect(image1, res * rgb_uvs[2]+jitter8[i]).a * m;
     }
    }
  } else if (samples < 6) {
    float m = 0.066667;
    for(int i=0;i<15;i++)
    {
     tp.r += texture2DRect(image1, res * rgb_uvs[0]+jitter15[i]).r * m;
     tp.g += texture2DRect(image1, res * rgb_uvs[1]+jitter15[i]).g * m;
     tp.b += texture2DRect(image1, res * rgb_uvs[2]+jitter15[i]).b * m;
     if (rgb_uvs[0].x >= 1.0 || rgb_uvs[0].x < 0.0 || rgb_uvs[0].y >= 1.0 || rgb_uvs[0].y < 0.0) { // Out of bounds
      tp.a += 0.0;
     } else {
     tp.a += texture2DRect(image1, res * rgb_uvs[2]+jitter15[i]).a * m;
     }
    }
  } else if (samples < 7) {
    float m = 0.041667;
    for(int i=0;i<24;i++)
    {
     tp.r += texture2DRect(image1, res * rgb_uvs[0]+jitter24[i]).r * m;
     tp.g += texture2DRect(image1, res * rgb_uvs[1]+jitter24[i]).g * m;
     tp.b += texture2DRect(image1, res * rgb_uvs[2]+jitter24[i]).b * m;
     if (rgb_uvs[0].x >= 1.0 || rgb_uvs[0].x < 0.0 || rgb_uvs[0].y >= 1.0 || rgb_uvs[0].y < 0.0) { // Out of bounds
      tp.a += 0.0;
     } else {
     tp.a += texture2DRect(image1, res * rgb_uvs[2]+jitter24[i]).a * m;
     }
    }
  } else {
    float m = 0.015152;
    for(int i=0;i<66;i++)
    {
     tp.r += texture2DRect(image1, res * rgb_uvs[0]+jitter66[i]).r * m;
     tp.g += texture2DRect(image1, res * rgb_uvs[1]+jitter66[i]).g * m;
     tp.b += texture2DRect(image1, res * rgb_uvs[2]+jitter66[i]).b * m;
     if (rgb_uvs[0].x >= 1.0 || rgb_uvs[0].x < 0.0 || rgb_uvs[0].y >= 1.0 || rgb_uvs[0].y < 0.0) { // Out of bounds
      tp.a += 0.0;
     } else {
     tp.a += texture2DRect(image1, res * rgb_uvs[2]+jitter66[i]).a * m;
     }
    }
  }
   // Alpha from the image2's R channel
   
   // and assign to the output
   gl_FragColor.rgba = tp;
}
