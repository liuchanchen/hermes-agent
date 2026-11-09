#include <cuda.h>

#include <inttypes.h>
#include <stdio.h>

static int get_attr(CUdevice device, CUdevice_attribute attr, const char *name)
{
    int value = -1;
    CUresult result = cuDeviceGetAttribute(&value, attr, device);

    if (result == CUDA_SUCCESS) {
        printf("  %-40s %d\n", name, value);
        return value;
    }

    const char *error = "unknown";
    cuGetErrorString(result, &error);
    printf("  %-40s error %d (%s)\n", name, (int)result, error);
    return -1;
}

int main(void)
{
    CUresult result = cuInit(0);
    if (result != CUDA_SUCCESS) {
        const char *error = "unknown";
        cuGetErrorString(result, &error);
        fprintf(stderr, "cuInit failed: %d (%s)\n", (int)result, error);
        return 1;
    }

    int count = 0;
    result = cuDeviceGetCount(&count);
    if (result != CUDA_SUCCESS) {
        fprintf(stderr, "cuDeviceGetCount failed: %d\n", (int)result);
        return 1;
    }

    for (int ordinal = 0; ordinal < count; ++ordinal) {
        CUdevice device;
        char name[256] = {0};
        int bus = -1;
        int slot = -1;

        if (cuDeviceGet(&device, ordinal) != CUDA_SUCCESS)
            continue;
        cuDeviceGetName(name, sizeof(name), device);
        cuDeviceGetAttribute(&bus, CU_DEVICE_ATTRIBUTE_PCI_BUS_ID, device);
        cuDeviceGetAttribute(&slot, CU_DEVICE_ATTRIBUTE_PCI_DEVICE_ID, device);

        printf("GPU %d: %s (%02x:%02x.0)\n", ordinal, name, bus, slot);
        get_attr(device, CU_DEVICE_ATTRIBUTE_GPU_DIRECT_RDMA_SUPPORTED,
                 "GPU_DIRECT_RDMA_SUPPORTED");
        get_attr(device,
                 CU_DEVICE_ATTRIBUTE_GPU_DIRECT_RDMA_WITH_CUDA_VMM_SUPPORTED,
                 "GPU_DIRECT_RDMA_WITH_CUDA_VMM_SUPPORTED");
        get_attr(device, CU_DEVICE_ATTRIBUTE_DMA_BUF_SUPPORTED,
                 "DMA_BUF_SUPPORTED");
        get_attr(device,
                 CU_DEVICE_ATTRIBUTE_GPU_DIRECT_RDMA_FLUSH_WRITES_OPTIONS,
                 "GPU_DIRECT_RDMA_FLUSH_WRITES_OPTIONS");
        get_attr(device, CU_DEVICE_ATTRIBUTE_GPU_DIRECT_RDMA_WRITES_ORDERING,
                 "GPU_DIRECT_RDMA_WRITES_ORDERING");

        CUcontext context = NULL;
        CUdeviceptr ptr = 0;
        int capable = -1;

        result = cuDevicePrimaryCtxRetain(&context, device);
        if (result == CUDA_SUCCESS)
            result = cuCtxSetCurrent(context);
        if (result == CUDA_SUCCESS)
            result = cuMemAlloc(&ptr, 128 * 1024);
        if (result == CUDA_SUCCESS)
            result = cuPointerGetAttribute(
                &capable, CU_POINTER_ATTRIBUTE_IS_GPU_DIRECT_RDMA_CAPABLE,
                ptr);

        if (result == CUDA_SUCCESS) {
            printf("  %-40s %d\n", "ALLOCATED_POINTER_GDR_CAPABLE", capable);
        } else {
            const char *error = "unknown";
            cuGetErrorString(result, &error);
            printf("  %-40s error %d (%s)\n",
                   "ALLOCATED_POINTER_GDR_CAPABLE", (int)result, error);
        }

        if (ptr != 0)
            cuMemFree(ptr);
        if (context != NULL) {
            cuCtxSetCurrent(NULL);
            cuDevicePrimaryCtxRelease(device);
        }
    }

    return 0;
}
