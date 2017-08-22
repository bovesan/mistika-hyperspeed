#version 130

#extension GL_ARB_texture_rectangle : enable
#extension GL_EXT_gpu_shader4 : enable

// Written by Bengt Ove Sannes (c) 2015
// bove@bengtove.com

uniform sampler2DRect image1;
uniform sampler2DRect image2;

uniform vec3 param1;
uniform vec3 param2;
uniform vec3 param3;
uniform vec3 param4;
uniform vec3 param5;

void main()
{
    float pass = int(param1.x);
    vec2 res = gl_TexCoord[0].zw;
    float aspect = res.x/res.y;
    int sampleSize = 10, offsetX, offsetY, threadsPerBound = 100;
    float left, right, top, bottom, modulo, limit;
    bool doubleBreak;
    
    vec2 pos = gl_TexCoord[0].xy;
    int halign = int(param1.y);
    int valign = int(param1.z);
    float movex = (param2.x*0.01-0.5)*res.x;
    float movey = (param2.y*0.01-0.5)*res.y;
    int axis = int(param5.z);
	// 0 = both, 1 = horizontal, 2 = vertical
    
    float tx, ty;
   
    vec4 pipe;
    
    if (pass == 0) {
        if((pos.x < 1 * threadsPerBound) && (pos.y <= 1.0) && (axis != 2)){
            // left
            modulo = mod(pos.x, float(threadsPerBound));
            offsetX = int(mod(modulo, 10.0));
            offsetY = int(floor(modulo * 0.1));
            doubleBreak = false;
            for(int x = offsetX; x <= res.x; x+=sampleSize){
                for(int y = offsetY; y <= res.y; y+=sampleSize){
                    if (texture2DRect(image1, vec2(x, y)).a > 0.0) {
                        left = x;
                        gl_FragColor = vec4(left/res.x);
                        doubleBreak = true;
                    }
                }
            if (doubleBreak) { break; } 
            }
        }
        else if((pos.x < 2 * threadsPerBound) && (pos.y <= 1.0) && (axis != 2)){
            // right
            modulo = mod(pos.x, float(threadsPerBound));
            offsetX = int(mod(modulo, 10.0));
            offsetY = int(floor(modulo * 0.1));
            doubleBreak = false;
            for(int x = int(res.x - offsetX); x >= 0; x-=sampleSize){
                for(int y = offsetY; y <= res.y; y+=sampleSize){
                    if (texture2DRect(image1, vec2(x, y)).a > 0.0) {
                        right = x;
                        gl_FragColor = vec4(right/res.x);
                        doubleBreak = true;
                    }
                }
            if (doubleBreak) { break; } 
            }
        }
        else if((pos.x < 3 * threadsPerBound) && (pos.y <= 1.0) && (axis != 1)){
            // bottom
            modulo = mod(pos.x, float(threadsPerBound));
            offsetX = int(mod(modulo, 10.0));
            offsetY = int(floor(modulo * 0.1));
            doubleBreak = false;
            for(int y = offsetY; y <= res.y; y+=sampleSize){
                for(int x = offsetX; x <= res.x; x+=sampleSize){
                    if (texture2DRect(image1, vec2(x, y)).a > 0.0) {
                        bottom = y;
                        gl_FragColor = vec4(bottom/res.y);
                        doubleBreak = true;
                    }
                }
            if (doubleBreak) { break; } 
            }
        }
        else if((pos.x < 4 * threadsPerBound) && (pos.y <= 1.0) && (axis != 1)){
            // top
            modulo = mod(pos.x, float(threadsPerBound));
            offsetX = int(mod(modulo, 10.0));
            offsetY = int(floor(modulo * 0.1));
            doubleBreak = false;
            for(int y = int(res.y - offsetY); y >= 0; y-=sampleSize){
                for(int x = offsetX; x <= res.x; x+=sampleSize){
                    if (texture2DRect(image1, vec2(x, y)).a > 0.0) {
                        top = y;
                        gl_FragColor = vec4(top/res.y);
                        doubleBreak = true;
                    }
                }
            if (doubleBreak) { break; } 
            }
        }
        else{
            gl_FragColor = texture2DRect(image1, pos.xy);
        }
    }
    else if (pass == 1) {
        if((pos.x < 1.0) && (pos.y <= 1.0) && (axis != 2)){
            // left
            limit = 1.0;
            for (int x = 0*threadsPerBound; x < threadsPerBound; x++) {
                limit = min(texture2DRect(image1, vec2(x, 0)).a, limit);
            }
            gl_FragColor = vec4(limit);
        }
        else if((pos.x < 2.0) && (pos.y <= 1.0) && (axis != 2)){
            // right
            limit = 0.0;
            for (int x = 1*threadsPerBound; x < threadsPerBound*2; x++) {
                limit = max(texture2DRect(image1, vec2(x, 0)).a, limit);
            }
            gl_FragColor = vec4(limit);
        }
        else if((pos.x < 3.0) && (pos.y <= 1.0) && (axis != 1)){
            // bottom
            limit = 1.0;
            for (int x = 2*threadsPerBound; x < threadsPerBound*3; x++) {
                limit = min(texture2DRect(image1, vec2(x, 0)).a, limit);
            }
            gl_FragColor = vec4(limit);
        }
        else if((pos.x < 4.0) && (pos.y <= 1.0) && (axis != 1)){
            // top
            limit = 0.0;
            for (int x = 3*threadsPerBound; x < threadsPerBound*4; x++) {
                limit = max(texture2DRect(image1, vec2(x, 0)).a, limit);
            }
            gl_FragColor = vec4(limit);
        }
        else if((pos.x < 4 * threadsPerBound) && (pos.y <= 1.0)){
            gl_FragColor = vec4(0.0);
        }
        else{
            gl_FragColor = texture2DRect(image1, pos.xy);
        }
    }
    else if (pass == 2) {
        if (texture2DRect(image2, vec2(1,0)).a == 0) {
            // No opaque pixels found
            gl_FragColor = vec4(0.0);
        }
        else {
			left = texture2DRect(image2, vec2(0,0)).a;
			right = texture2DRect(image2, vec2(1,0)).a;
			bottom = texture2DRect(image2, vec2(2,0)).a;
			top = texture2DRect(image2, vec2(3,0)).a;
            left = left*res.x;
            right = right*res.x;
            bottom = bottom*res.y;
            top = top*res.y;
			if (halign == 1) {
				tx = pos.x - movex + left;
			} else if (halign == 2) {
				tx = pos.x - movex + ((right + left - res.x) * 0.5);
			} else if (halign == 3) {
				tx = pos.x - movex + right - res.x;
			} else {
				tx = pos.x - movex;
			}
			if (valign == 1) {
				ty = pos.y - movey + top - res.y;
			} else if (valign == 2) {
				ty = pos.y - movey + ((bottom + top - res.y) * 0.5);
			} else if (valign == 3) {
				ty = pos.y - movey + bottom;
			} else {
				ty = pos.y - movey;
			}
			if (ty < 0.0 || ty > res.y || tx < 0.0 || tx > res.x) {
				gl_FragColor = vec4(0.0);
			} else {
				gl_FragColor = texture2DRect(image1, vec2(tx, ty));
			}
        }
    }
}
