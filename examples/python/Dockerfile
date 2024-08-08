FROM jupyter/datascience-notebook:latest

ENTRYPOINT ["/bin/bash"]

CMD [ "-c", "python -m ipykernel_launcher -f $PODKERNEL_CONNECTION_FILE" ]
