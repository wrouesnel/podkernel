# Podkernel

Use Podman images as Jupyter Kernels. Inspired by [dockernel](https://github.com/MrMino/dockernel).

## Installation

```
pip install --user git+https://github.com/wrouesnel/podkernel@main
```

## Usage

The basic requirement is that your target container image *must* start a compatible Jupyter kernel
process on the command line, and receive an environment variable named `PODKERNEL_CONNECTION_FILE`
which contains the path to the connection file from the server process.

Kernels are installed with the `install` command:

```
podkernel install [podman run args] -- [container command args]
```

An example using the datascience notebook container:

```
podkernel install \
    jupyter/datascience-notebook:latest '--entrypoint=["/bin/bash", "-c"]' -- 'python -m ipykernel_launcher -f $PODKERNEL_CONNECTION_FILE'
```

Note the use of the inline JSON syntax which is supported by the `podman` CLI but requires special escaping of the argument.
Other than the `--` separator, these arguments are passed directly through to the podman CLI - any valid podman CLI
`run` argument is valid here.

When a new kernel is started with this configuration, it will be executed with the `[podman run args]` plus some extra parameters
to enable it to function seamlessly as an IPython kernel.

The more useful version of this is to install kernels which are built from a `Containerfile` or `Dockerfile` on your
system. This can be requested by passing the `--build` argument in which case it is expected that the `IMAGE` parameter
is a path to a directory.

The command line layout also gains sections in this mode:

````
podkernel install --build <path to build directory>  [podman build args] -- [podman run args] -- [container command args]
````

For simple configurations (which should be the common case since you have control of your own Containerfiles), most
of these arguments can be omitted.

```
podkernel install --build ~/jupyter-container-kernels/python
```

In this case we've emitted all the arguments, since we're just asking for a container build and run. If we wanted
to include run or command arguments we would need to include `--` separators:

```
podkernel install --build ~/jupyter-container-kernels/python -- -v $HOME:$HOME -- bash
```

*Important*: due to the comand line parser, build-args also need a leading `--` separator:

```
podkernel install --build ~/jupyter-container-kernels/python -- --build-arg=somearg=somevalue -- -v $HOME:$HOME -- bash
```

## Quirks

This application works by manipulating `docker` or `podman` command lines directly, rather than the APIs in order to provide
a consistent and extensible interfaces. Several arguments will always be modified in order to allow it to function:

* `--env` : this is always set with PODKERNEL_CONNECTION_FILE
* `--port`: this always receives localhost port bindings from the connection file (to allow the server to connect)
* `--volume`: this is always modified to bind the path of `PODKERNEL_CONNECTION_FILE` into the container
* `IMAGE`: this is always set the image ID of the image for any given invocation - i.e. a given build output.

The benefit of this approach is kernels may have arbitrarily complicated command lines, and automatically support
new features. The primary motivation to develop this application was to provide an easy way to use machine-learning
enabled docker images with passthrough to the system GPU.

## Persistence

By default containers are deleted on exit - every new kernel invocation is a new container.

Complete control over the container launch environment though makes providing persistence very easy: simply specify
additional `-v` `--volume` mount commands as part of your container run arguments, and set them to fixed containers.

## Examples

### ROCm example kernel

This is a practical example of using a ROCm enabled container with GPU passthrough under rootless podman, including
bringing in build and run arguments for certificates and proxies (I use a MITM SQUID instance to cache packages).

```
podkernel install --build ~/opt/jupyter-container-kernels/rocm-python -- \
    -v /etc/ssl/certs:/etc/ssl/certs:ro
    --
    -v /etc/ssl/certs:/etc/ssl/certs:ro
    --device=/dev/kfd \
    --device=/dev/dri \
    --ipc=host \
    --group-add keep-groups \
    --cap-add=SYS_PTRACE \
    --security-opt seccomp=unconfined \
    --shm-size 8G \
    --user=root
```
