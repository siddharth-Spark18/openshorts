// CUDA kernels for osrender. Planes are NV12: luma (1 byte per pixel) and
// interleaved chroma (U,V per pixel at half resolution). Regenerate the PTX
// with:  nvcc -ptx -O3 -arch=compute_75 src/kernels.cu -o src/kernels.ptx

// swscale's default bicubic (B = 0, C = 0.6).
__device__ __forceinline__ float cubic(float x) {
    x = fabsf(x);
    if (x < 1.f) return (8.4f * x * x * x - 14.4f * x * x + 6.f) * (1.f / 6.f);
    if (x < 2.f) return (-3.6f * x * x * x + 18.f * x * x - 28.8f * x + 14.4f) * (1.f / 6.f);
    return 0.f;
}

// Scale the source rectangle (sx, sy, sw_, sh_ in this plane's pixels) into
// the destination rectangle (ox, oy, ow, oh) with a bicubic filter whose
// support widens with the reduction, like swscale, so shrinking does not alias.
extern "C" __global__ void resample(const unsigned char* src, int sp, int sw, int sh,
                                    unsigned char* dst, int dp, int dw, int dh,
                                    float sx, float sy, float sw_, float sh_,
                                    int ox, int oy, int ow, int oh, int step) {
    int x = blockIdx.x * blockDim.x + threadIdx.x, y = blockIdx.y * blockDim.y + threadIdx.y;
    if (x >= ow || y >= oh) return;
    int tx = ox + x, ty = oy + y;
    if (tx < 0 || ty < 0 || tx >= dw || ty >= dh) return;
    float kx = sw_ / ow, ky = sh_ / oh;
    float fx = fmaxf(kx, 1.f), fy = fmaxf(ky, 1.f);
    float cx = sx + (x + 0.5f) * kx - 0.5f, cy = sy + (y + 0.5f) * ky - 0.5f;
    int x0 = (int)floorf(cx - 2.f * fx) + 1, x1 = (int)floorf(cx + 2.f * fx);
    int y0 = (int)floorf(cy - 2.f * fy) + 1, y1 = (int)floorf(cy + 2.f * fy);
    for (int c = 0; c < step; c++) {
        float acc = 0.f, wsum = 0.f;
        for (int j = y0; j <= y1; j++) {
            float wy = cubic((j - cy) / fy);
            if (wy == 0.f) continue;
            int yy = min(max(j, 0), sh - 1);
            for (int i = x0; i <= x1; i++) {
                float w = wy * cubic((i - cx) / fx);
                int xx = min(max(i, 0), sw - 1);
                acc += w * src[yy * sp + xx * step + c];
                wsum += w;
            }
        }
        float v = wsum != 0.f ? acc / wsum : 0.f;
        dst[ty * dp + tx * step + c] = (unsigned char)fminf(fmaxf(v + 0.5f, 0.f), 255.f);
    }
}

// One direction of a separable Gaussian blur over a whole plane.
extern "C" __global__ void blur(const unsigned char* src, unsigned char* dst, int pitch,
                                int w, int h, int step, float sigma, int horizontal) {
    int x = blockIdx.x * blockDim.x + threadIdx.x, y = blockIdx.y * blockDim.y + threadIdx.y;
    if (x >= w || y >= h) return;
    int r = (int)ceilf(3.f * sigma);
    float k = -0.5f / (sigma * sigma);
    for (int c = 0; c < step; c++) {
        float acc = 0.f, wsum = 0.f;
        for (int i = -r; i <= r; i++) {
            int xx = horizontal ? min(max(x + i, 0), w - 1) : x;
            int yy = horizontal ? y : min(max(y + i, 0), h - 1);
            float wt = __expf(i * i * k);
            acc += wt * src[yy * pitch + xx * step + c];
            wsum += wt;
        }
        dst[y * pitch + x * step + c] = (unsigned char)(acc / wsum + 0.5f);
    }
}

// Alpha-blend a pre-converted overlay plane (values + alpha, tightly packed
// at the plane's size) onto a plane of the frame.
extern "C" __global__ void blend(unsigned char* dst, int dp, int w, int h, int step,
                                 const unsigned char* ov, const unsigned char* oa) {
    int x = blockIdx.x * blockDim.x + threadIdx.x, y = blockIdx.y * blockDim.y + threadIdx.y;
    if (x >= w || y >= h) return;
    float a = oa[y * w + x] * (1.f / 255.f);
    if (a <= 0.f) return;
    for (int c = 0; c < step; c++) {
        float v = dst[y * dp + x * step + c];
        dst[y * dp + x * step + c] =
            (unsigned char)(v * (1 - a) + ov[(y * w + x) * step + c] * a + 0.5f);
    }
}
