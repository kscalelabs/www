import ImageComponent from "components/files/ViewImage";
import { components } from "gen/api";
import { useAlertQueue } from "hooks/alerts";
import { useAuthentication } from "hooks/auth";
import { useEffect, useState } from "react";
import { Carousel, Row, Spinner } from "react-bootstrap";

const EmptyCarouselItem = ({ loading }: { loading: boolean }) => {
  // TODO: Render a better default loading state.
  return (
    <Carousel.Item>
      <div
        style={{
          display: "flex",
          alignItems: "center",
          justifyContent: "center",
          overflow: "hidden",
        }}
      >
        {loading ? <Spinner animation="border" /> : <p>No artifacts</p>}
      </div>
    </Carousel.Item>
  );
};

interface Props {
  listing_id: string;
  edit: boolean;
}

const ListingArtifacts = (props: Props) => {
  const { listing_id } = props;

  const auth = useAuthentication();
  const { addErrorAlert } = useAlertQueue();

  const [artifacts, setArtifacts] = useState<
    components["schemas"]["ListArtifactsResponse"] | null
  >(null);

  useEffect(() => {
    const fetchArtifacts = async () => {
      const { data, error } = await auth.client.GET("/artifacts/{listing_id}", {
        params: {
          path: { listing_id },
        },
      });

      if (error) {
        addErrorAlert(error);
      } else {
        setArtifacts(data);
      }
    };
    fetchArtifacts();
  }, [listing_id]);

  return (
    <Row className="mb-3">
      <Carousel
        indicators
        data-bs-theme="dark"
        style={{ border: "1px solid #ccc" }}
        interval={null}
        controls={artifacts !== null && artifacts.artifacts.length > 1}
      >
        {artifacts === null || artifacts.artifacts.length === 0 ? (
          <EmptyCarouselItem loading={true} />
        ) : (
          artifacts.artifacts.map((artifact, key) => (
            <Carousel.Item key={key}>
              <div
                style={{
                  display: "flex",
                  alignItems: "center",
                  justifyContent: "center",
                  overflow: "hidden",
                }}
              >
                {artifact.artifact_type === "image" ? (
                  <ImageComponent
                    imageId={artifact.artifact_id}
                    size={"large"}
                    caption={"caption"}
                  />
                ) : (
                  <p>Unhandled artifact type: {artifact.artifact_type}</p>
                )}
              </div>
              <Carousel.Caption
                style={{
                  backgroundColor: "rgba(255, 255, 255, 0.5)",
                  color: "black",
                  padding: "0.1rem",
                  // Put the caption at the top
                  top: 10,
                  bottom: "unset",
                }}
              >
                {artifact.description}
              </Carousel.Caption>
            </Carousel.Item>
          ))
        )}
      </Carousel>
    </Row>
  );
};

export default ListingArtifacts;